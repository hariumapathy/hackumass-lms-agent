"""Request dependencies.

`current_user` is a STUB for S02: it only checks that a bearer token is present and returns a
fixed demo user. Real Supabase JWT verification replaces it in S20 (same signature).
"""

from uuid import UUID

from fastapi import Header
from pydantic import BaseModel

from app.core.errors import AppError

DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class UserCtx(BaseModel):
    user_id: UUID
    email: str | None = None


async def current_user(authorization: str | None = Header(default=None)) -> UserCtx:
    if (
        not authorization
        or not authorization.lower().startswith("bearer ")
        or not authorization[7:].strip()
    ):
        raise AppError("unauthorized", "Missing or invalid bearer token", status=401)
    return UserCtx(user_id=DEMO_USER_ID, email="demo@example.com")
