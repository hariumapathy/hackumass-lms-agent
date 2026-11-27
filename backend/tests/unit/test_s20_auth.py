"""S20: API skeleton and auth (JWT verification, route + repository scans, errors, rate limit,
logging). DB-backed tests (S20-T05, S20-T07) live in tests/integration/test_s20_db.py."""

import importlib
import inspect
import json
import logging
import pkgutil
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

from app.api.deps import UserCtx, current_user
from app.core.auth import TokenVerifier
from app.core.clock import FixedClock
from app.core.errors import AppError
from app.core.ratelimit import TokenBucket
from app.main import create_app
from tests.helpers import TEST_ISSUER, TEST_JWT_SECRET, TEST_USER_ID, auth_header, make_token

PUBLIC_ROUTES = {("GET", "/health"), ("GET", "/calendar/{token}.ics")}
JWKS_URL = "https://example.supabase.co/auth/v1/.well-known/jwks.json"
T0 = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def hs_verifier(clock: FixedClock | None = None) -> TokenVerifier:
    return TokenVerifier(
        issuer=TEST_ISSUER, jwks_url=None, hs256_secret=TEST_JWT_SECRET, clock=clock
    )


# --- S20-T01: valid HS256 token -> UserCtx; wrong secret -> 401 ---------------------------


async def test_s20_t01_valid_hs256_token_returns_user_ctx() -> None:
    ctx = await hs_verifier().verify(make_token(TEST_USER_ID, email="a@umass.edu"))
    assert ctx == UserCtx(user_id=TEST_USER_ID, email="a@umass.edu")


async def test_s20_t01_wrong_secret_is_401() -> None:
    token = make_token(secret="another-secret-that-is-also-32-bytes-long!!")
    with pytest.raises(AppError) as err:
        await hs_verifier().verify(token)
    assert err.value.status == 401 and err.value.code == "unauthorized"


def test_s20_t01_current_user_dependency_uses_real_token(client: TestClient) -> None:
    r = client.get("/me", headers=auth_header(TEST_USER_ID))
    assert r.status_code == 200
    assert r.json()["user_id"] == str(TEST_USER_ID)
    assert client.get("/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_s20_t01_current_user_signature_unchanged() -> None:
    params = inspect.signature(current_user).parameters
    assert list(params) == ["authorization"]


# --- JWKS (asymmetric, what the hosted Supabase project uses) -----------------------------


def _es256_key_and_jwks(kid: str = "kid-1") -> tuple[ec.EllipticCurvePrivateKey, dict]:
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(ECAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return key, {"keys": [jwk]}


def _es256_token(key: ec.EllipticCurvePrivateKey, kid: str = "kid-1", **claims: object) -> str:
    now = int(datetime.now(UTC).timestamp())
    body = {
        "iss": TEST_ISSUER,
        "sub": str(TEST_USER_ID),
        "aud": "authenticated",
        "exp": now + 3600,
        **claims,
    }
    return jwt.encode(body, key, algorithm="ES256", headers={"kid": kid})


@respx.mock
async def test_s20_t01_jwks_es256_token_verifies_and_jwks_is_cached_10_min() -> None:
    key, jwks = _es256_key_and_jwks()
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    clock = FixedClock(T0)
    verifier = TokenVerifier(issuer=TEST_ISSUER, jwks_url=JWKS_URL, hs256_secret=None, clock=clock)

    token = _es256_token(key)
    assert (await verifier.verify(token)).user_id == TEST_USER_ID
    await verifier.verify(token)
    assert route.call_count == 1  # cached

    clock.advance(timedelta(minutes=11))
    await verifier.verify(token)
    assert route.call_count == 2  # refreshed after the 10-minute TTL


@respx.mock
async def test_s20_t01_jwks_unknown_kid_or_wrong_key_is_401() -> None:
    _, jwks = _es256_key_and_jwks("kid-1")
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    verifier = TokenVerifier(
        issuer=TEST_ISSUER, jwks_url=JWKS_URL, hs256_secret=None, clock=FixedClock(T0)
    )
    other_key = ec.generate_private_key(ec.SECP256R1())
    for token in (_es256_token(other_key, kid="kid-unknown"), _es256_token(other_key)):
        with pytest.raises(AppError) as err:
            await verifier.verify(token)
        assert err.value.status == 401


@respx.mock
async def test_s20_t01_jwks_with_hs256_fallback_accepts_legacy_tokens() -> None:
    _, jwks = _es256_key_and_jwks()
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    verifier = TokenVerifier(
        issuer=TEST_ISSUER, jwks_url=JWKS_URL, hs256_secret=TEST_JWT_SECRET, clock=FixedClock(T0)
    )
    assert (await verifier.verify(make_token())).user_id == TEST_USER_ID


async def test_s20_t01_hs256_token_rejected_when_only_jwks_configured() -> None:
    verifier = TokenVerifier(
        issuer=TEST_ISSUER, jwks_url=JWKS_URL, hs256_secret=None, clock=FixedClock(T0)
    )
    with pytest.raises(AppError) as err:
        await verifier.verify(make_token())
    assert err.value.status == 401


@respx.mock
async def test_s20_t01_jwks_endpoint_down_is_retryable_503() -> None:
    _, _ = _es256_key_and_jwks()
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("down"))
    verifier = TokenVerifier(
        issuer=TEST_ISSUER, jwks_url=JWKS_URL, hs256_secret=None, clock=FixedClock(T0)
    )
    key, _ = _es256_key_and_jwks()
    with pytest.raises(AppError) as err:
        await verifier.verify(_es256_token(key))
    assert err.value.status == 503 and err.value.retryable is True


# --- S20-T02: expired / wrong audience / malformed -> 401 ---------------------------------


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp_in=-60),
        make_token(aud="anon"),
        make_token(sub="not-a-uuid"),
        jwt.encode({"aud": "authenticated", "exp": 4102444800}, TEST_JWT_SECRET, "HS256"),
        jwt.encode({"sub": str(TEST_USER_ID), "aud": "authenticated"}, TEST_JWT_SECRET, "HS256"),
        jwt.encode({"sub": str(TEST_USER_ID), "aud": "authenticated"}, "", "none"),
        "",
        "abc.def.ghi",
    ],
    ids=["expired", "wrong-aud", "bad-sub", "no-sub", "no-exp", "alg-none", "empty", "garbage"],
)
async def test_s20_t02_bad_tokens_are_401(token: str) -> None:
    with pytest.raises(AppError) as err:
        await hs_verifier().verify(token)
    assert err.value.status == 401 and err.value.code == "unauthorized"


@pytest.mark.parametrize("header", [None, "", "Bearer ", "Basic abc", "bearer"])
def test_s20_t02_missing_or_malformed_header_is_401(client: TestClient, header: str | None) -> None:
    headers = {} if header is None else {"Authorization": header}
    r = client.get("/me", headers=headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_s20_t02_expired_token_via_api_is_401(client: TestClient) -> None:
    r = client.get("/me", headers=auth_header(exp_in=-5))
    assert r.status_code == 401


# --- S20-T03: every route except the public ones depends on current_user ------------------


def _depends_on(dependant, target) -> bool:  # noqa: ANN001
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def _api_routes(routes) -> list[APIRoute]:  # noqa: ANN001
    """Flatten routes, incl. FastAPI's lazily included routers (`original_router`)."""
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif (inner := getattr(route, "original_router", None)) is not None:
            found += _api_routes(inner.routes)
    return found


def test_s20_t03_every_non_public_route_requires_current_user() -> None:
    app = create_app()
    checked = 0
    for route in _api_routes(app.routes):
        for method in route.methods or ():
            requires = _depends_on(route.dependant, current_user)
            if (method, route.path) in PUBLIC_ROUTES:
                assert not requires, f"{method} {route.path} should be public"
            else:
                assert requires, f"{method} {route.path} is missing current_user"
            checked += 1
    assert checked >= 25


def test_s20_t03_every_non_public_operation_returns_401_without_token(client: TestClient) -> None:
    """Behavioral twin of the scan above, driven by the OpenAPI document."""
    paths = client.get("/openapi.json").json()["paths"]
    checked = 0
    for path, ops in paths.items():
        concrete = (
            path.replace("{platform}", "canvas")
            .replace("{token}", "demo-token")
            .replace("{", "")
            .replace("}", "")
        )
        concrete = "/".join(
            "00000000-0000-4000-8000-000000000000" if part.endswith("_id") else part
            for part in concrete.split("/")
        )
        for method in ops:
            r = client.request(method.upper(), concrete, json={})
            if (method.upper(), path) in PUBLIC_ROUTES:
                assert r.status_code != 401, f"{method} {path} should be public"
            else:
                assert r.status_code == 401, f"{method} {path} -> {r.status_code}"
            checked += 1
    assert checked >= 25


# --- S20-T04: every repository function takes user_id as its first data parameter --------


def test_s20_t04_repository_functions_take_user_id_first() -> None:
    import app.db.repositories as repos

    functions = []
    for info in pkgutil.iter_modules(repos.__path__):
        module = importlib.import_module(f"{repos.__name__}.{info.name}")
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if fn.__module__ != module.__name__ or name.startswith("_"):
                continue
            functions.append(fn)
            params = list(inspect.signature(fn).parameters)
            assert params[:2] == ["conn", "user_id"], f"{module.__name__}.{name}{params}"
    assert functions, "no repository functions found"


# --- S20-T06: error envelope for 401, 404, 422, 500 ----------------------------------------


def test_s20_t06_error_envelope_shapes() -> None:
    app = create_app()

    @app.get("/_boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    client = TestClient(app, raise_server_exceptions=False)
    h = auth_header()
    cases = [
        (client.get("/me"), 401, "unauthorized"),
        (
            client.get("/conversations/00000000-0000-4000-8000-00000000ffff", headers=h),
            404,
            "not_found",
        ),
        (client.get("/nope", headers=h), 404, "not_found"),
        (client.post("/chat", json={"message": ""}, headers=h), 422, "validation_error"),
        (client.get("/_boom"), 500, "internal"),
    ]
    for r, status, code in cases:
        assert r.status_code == status, r.text
        err = r.json()["error"]
        assert err["code"] == code and isinstance(err["message"], str)
        assert isinstance(err["retryable"], bool)
        assert "secret internals" not in r.text and "Traceback" not in r.text


# --- S20-T08: PATCH /me validation -----------------------------------------------------------


def test_s20_t08_patch_me_rejects_bad_timezone_and_unknown_model(client: TestClient) -> None:
    h = auth_header()
    bad_tz = client.patch("/me", json={"timezone": "Mars/Olympus"}, headers=h)
    assert bad_tz.status_code == 422 and bad_tz.json()["error"]["code"] == "validation_error"
    bad_model = client.patch("/me", json={"model_choice": "evil/model"}, headers=h)
    assert bad_model.status_code == 422
    assert bad_model.json()["error"]["code"] == "validation_error"


def test_s20_t08_patch_me_accepts_valid_values(client: TestClient) -> None:
    h = auth_header()
    model_id = client.get("/models", headers=h).json()["models"][0]["id"]
    r = client.patch(
        "/me", json={"timezone": "America/Los_Angeles", "model_choice": model_id}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "America/Los_Angeles"


# --- S20-T09: chat rate limit ------------------------------------------------------------------


def test_s20_t09_token_bucket_10_per_minute() -> None:
    clock = FixedClock(T0)
    bucket = TokenBucket(capacity=10, per_seconds=60, clock=clock)
    assert all(bucket.allow("u1") for _ in range(10))
    assert not bucket.allow("u1")
    assert bucket.allow("u2")  # per user
    clock.advance(timedelta(seconds=6))  # refills one token every 6 s
    assert bucket.allow("u1")
    assert not bucket.allow("u1")


def test_s20_t09_chat_returns_429_after_10_requests_per_minute() -> None:
    client = TestClient(create_app(clock=FixedClock(T0)), raise_server_exceptions=False)
    h = auth_header()
    for _ in range(10):
        assert client.post("/chat", json={"message": "hi"}, headers=h).status_code == 200
    r = client.post("/chat", json={"message": "hi"}, headers=h)
    assert r.status_code == 429
    assert r.json()["error"] == {
        "code": "rate_limited",
        "message": r.json()["error"]["message"],
        "retryable": True,
    }
    # another student is not affected
    other = auth_header(UUID("00000000-0000-4000-8000-0000000000c3"))
    assert client.post("/chat", json={"message": "hi"}, headers=other).status_code == 200


# --- S20-T10: logs never contain the Authorization header or message text ---------------------


def test_s20_t10_logs_have_no_tokens_or_message_text(caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    token = make_token()
    secret_text = "my private question about memoization xyzzy"
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/chat", json={"message": secret_text}, headers={"Authorization": f"Bearer {token}"}
        )
        client.get("/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert token not in caplog.text
    assert "invalid.token.value" not in caplog.text
    assert "xyzzy" not in caplog.text
    request_logs = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.request"]
    assert len(request_logs) == 2
    first = request_logs[0]
    assert first["route"] == "/chat" and first["method"] == "POST"
    assert first["user_id"] == str(TEST_USER_ID)
    assert first["status"] == 200 and "latency_ms" in first and first["request_id"]
    assert request_logs[1]["status"] == 401 and request_logs[1]["user_id"] is None


# --- DB unavailable -> retryable 503 (S20 edge case) ------------------------------------------


async def test_s20_db_unavailable_is_retryable_503(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    from app.db import pool

    async def broken_pool() -> None:
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(pool, "get_pool", broken_pool)
    with pytest.raises(AppError) as err:
        async with pool.connection():
            pass
    assert err.value.status == 503 and err.value.code == "internal" and err.value.retryable
