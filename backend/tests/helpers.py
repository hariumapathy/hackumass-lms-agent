"""Shared test helpers: mint Supabase-style JWTs without any network or real keys."""

import time
from typing import Any
from uuid import UUID

import jwt

TEST_JWT_SECRET = "test-only-hs256-secret-at-least-32-bytes-long!"
TEST_ISSUER = "http://127.0.0.1:54321/auth/v1"
TEST_USER_ID = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-0000000000b2")


def make_token(
    sub: UUID | str = TEST_USER_ID,
    *,
    email: str | None = "student@umass.edu",
    aud: str = "authenticated",
    exp_in: int = 3600,
    secret: str = TEST_JWT_SECRET,
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": str(sub),
        "aud": aud,
        "iat": now,
        "exp": now + exp_in,
        "iss": TEST_ISSUER,
    }
    if email is not None:
        claims["email"] = email
    claims.update(extra or {})
    return jwt.encode(claims, secret, algorithm="HS256")


def auth_header(sub: UUID | str = TEST_USER_ID, **kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub, **kwargs)}"}
