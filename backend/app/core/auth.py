"""Supabase access-token verification (S20).

Asymmetric tokens (ES256/RS256, what hosted Supabase issues) are checked against the project's
JWKS (`SUPABASE_JWKS_URL`, cached 10 min). Legacy HS256 tokens are checked with
`SUPABASE_JWT_SECRET` when it is set. Either way: `exp` and `aud="authenticated"` are required and
`sub` must be a UUID. Never log the token itself.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
from pydantic import BaseModel

from app.core.clock import Clock, SystemClock
from app.core.errors import AppError

log = logging.getLogger(__name__)

AUDIENCE = "authenticated"
ASYMMETRIC_ALGS = {"ES256", "RS256", "EdDSA"}
JWKS_TTL = timedelta(minutes=10)
UNKNOWN_KID_REFRESH = timedelta(seconds=30)


class UserCtx(BaseModel):
    user_id: UUID
    email: str | None = None


def unauthorized(message: str = "Please sign in again.") -> AppError:
    return AppError("unauthorized", message, status=401)


class TokenVerifier:
    def __init__(
        self,
        *,
        jwks_url: str | None,
        hs256_secret: str | None,
        clock: Clock | None = None,
        timeout_s: float = 5.0,
    ) -> None:
        self._jwks_url = jwks_url or None
        self._secret = hs256_secret or None
        self._clock = clock or SystemClock()
        self._timeout_s = timeout_s
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> UserCtx:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise unauthorized() from None
        alg = header.get("alg")
        if alg == "HS256" and self._secret:
            key: Any = self._secret
        elif alg in ASYMMETRIC_ALGS and self._jwks_url:
            key = (await self._signing_key(header.get("kid"))).key
        else:
            raise unauthorized()
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience=AUDIENCE,
                options={"require": ["exp", "sub", "aud"]},
            )
            user_id = UUID(str(claims["sub"]))
        except (jwt.PyJWTError, ValueError):
            raise unauthorized() from None
        email = claims.get("email")
        return UserCtx(user_id=user_id, email=email if isinstance(email, str) else None)

    async def _signing_key(self, kid: str | None) -> jwt.PyJWK:
        if not kid:
            raise unauthorized()
        async with self._lock:
            now = self._clock.now()
            expired = self._fetched_at is None or now - self._fetched_at >= JWKS_TTL
            # A rotated key: refetch early, but not more than every 30 s (no refetch storms).
            unknown = kid not in self._keys and (
                self._fetched_at is None or now - self._fetched_at >= UNKNOWN_KID_REFRESH
            )
            if expired or unknown:
                await self._fetch(now)
        found = self._keys.get(kid)
        if found is None:
            raise unauthorized()
        return found

    async def _fetch(self, now: datetime) -> None:
        assert self._jwks_url
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            log.warning("could not fetch JWKS")
            if self._keys:  # keep serving the last good keys
                return
            raise AppError(
                "internal", "Sign-in check is unavailable. Try again.", status=503, retryable=True
            ) from None
        keys: dict[str, jwt.PyJWK] = {}
        for jwk in data.get("keys", []):
            try:
                keys[jwk["kid"]] = jwt.PyJWK(jwk)
            except (jwt.PyJWTError, KeyError):
                continue
        self._keys, self._fetched_at = keys, now
