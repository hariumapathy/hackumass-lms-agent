"""Request dependencies (S20): authentication, DB connection, chat rate limit."""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
from psycopg import AsyncConnection

from app.core.auth import TokenVerifier, UserCtx, unauthorized
from app.core.errors import AppError
from app.core.logging import set_log_user
from app.core.ratelimit import TokenBucket
from app.core.settings import get_settings
from app.db.pool import connection

__all__ = ["UserCtx", "current_user", "db", "chat_rate_limit", "get_verifier"]


@lru_cache
def get_verifier() -> TokenVerifier:
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    return TokenVerifier(
        jwks_url=settings.supabase_jwks_url,
        hs256_secret=secret.get_secret_value() if secret else None,
        issuer=settings.expected_jwt_issuer,
    )


async def current_user(authorization: str | None = Header(default=None)) -> UserCtx:
    """Verify the Supabase access token; 401 on any failure. Never logs the token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized()
    token = authorization[7:].strip()
    if not token:
        raise unauthorized()
    user = await get_verifier().verify(token)
    set_log_user(str(user.user_id))
    return user


async def db() -> AsyncIterator[AsyncConnection]:
    async with connection() as conn:
        yield conn


async def chat_rate_limit(
    request: Request, user: Annotated[UserCtx, Depends(current_user)]
) -> None:
    """POST /chat: 10 requests/min per student (S20 rule 7)."""
    bucket: TokenBucket = request.app.state.chat_limiter
    if not bucket.allow(str(user.user_id)):
        raise AppError(
            "rate_limited",
            "You're sending messages quickly. Wait a few seconds and try again.",
            status=429,
            retryable=True,
        )
