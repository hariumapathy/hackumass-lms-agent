"""S38 issuer binding; synthetic signed tokens only."""

import json

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_verifier
from app.core.auth import TokenVerifier
from app.core.errors import AppError
from app.core.settings import get_settings
from app.main import create_app
from tests.helpers import TEST_JWT_SECRET, auth_header, make_token

ISSUER = "http://127.0.0.1:54321/auth/v1"


@pytest.mark.parametrize(
    "issuer", [None, "https://other.example/auth/v1", ISSUER + "/evil", [ISSUER]]
)
def test_S38_T01_api_rejects_wrong_missing_or_list_issuer(issuer):
    claims = jwt.decode(make_token(), options={"verify_signature": False})
    if issuer is not None:
        claims["iss"] = issuer
    else:
        claims.pop("iss", None)
    token = jwt.api_jws.encode(json.dumps(claims).encode(), TEST_JWT_SECRET, algorithm="HS256")
    with TestClient(create_app()) as client:
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_S38_T01_correct_api_issuer():
    with TestClient(create_app()) as client:
        assert client.get("/me", headers=auth_header(extra={"iss": ISSUER})).status_code == 200


async def test_S38_T02_hs_verifier_pins_issuer():
    verifier = TokenVerifier(jwks_url=None, hs256_secret=TEST_JWT_SECRET, issuer=ISSUER)
    await verifier.verify(make_token(extra={"iss": ISSUER}))
    with pytest.raises(AppError):
        await verifier.verify(make_token(extra={"iss": "https://other.example/auth/v1"}))


def test_S38_T03_trusted_override(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "https://custom.example/auth/v1")
    get_settings.cache_clear()
    get_verifier.cache_clear()
    with TestClient(create_app()) as client:
        assert client.get("/me", headers=auth_header(extra={"iss": ISSUER})).status_code == 401
        assert (
            client.get(
                "/me", headers=auth_header(extra={"iss": "https://custom.example/auth/v1"})
            ).status_code
            == 200
        )


def test_S38_T06_no_private_claims_in_error(caplog):
    token = make_token(extra={"iss": "https://wrong.example/private-claim"})
    with TestClient(create_app()) as client:
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert token not in response.text + caplog.text
    assert "private-claim" not in response.text + caplog.text


async def test_S38_T02_T04_es256_issuer_and_cache():
    import respx

    from tests.unit.test_s20_auth import JWKS_URL, _es256_key_and_jwks, _es256_token

    key, jwks = _es256_key_and_jwks()
    verifier = TokenVerifier(jwks_url=JWKS_URL, hs256_secret=None, issuer=ISSUER)
    with respx.mock:
        route = respx.get(JWKS_URL).respond(200, json=jwks)
        await verifier.verify(_es256_token(key, iss=ISSUER))
        with pytest.raises(AppError):
            await verifier.verify(_es256_token(key, iss="https://wrong.example/auth/v1"))
        assert route.call_count == 1


@pytest.mark.parametrize(
    "issuer",
    ["http://auth.example/auth/v1", "https://localhost/auth/v1", "https://auth.example/wrong"],
)
def test_S38_T05_production_override_validation(issuer):
    from pydantic import ValidationError

    from tests.unit.test_s37_production_config import production

    with pytest.raises(ValidationError, match="supabase_jwt_issuer"):
        production(supabase_jwt_issuer=issuer)
