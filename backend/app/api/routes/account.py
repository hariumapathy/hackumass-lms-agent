"""Account endpoints: /me, /me/data, /models (S20; picker S26). DB mode (DATA_SOURCE=db) uses
the S01 tables; mock mode returns the S02 demo student."""

from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user, data_user
from app.core.errors import AppError
from app.core.settings import get_settings
from app.db.pool import connection
from app.db.repositories import profiles
from app.db.repositories import sync as sync_repo

router = APIRouter(tags=["account"])
User = Annotated[UserCtx, Depends(data_user)]
DeletionUser = Annotated[UserCtx, Depends(current_user)]


def _db_mode() -> bool:
    return get_settings().data_source == "db"


async def _me_from_db(user: UserCtx) -> s.Me:
    async with connection() as conn:
        profile = await profiles.ensure_profile(conn, user.user_id, user.email)  # S20 rule
        rows = await sync_repo.list_connections(conn, user.user_id)
    return s.Me(
        user_id=user.user_id,
        display_name=profile.display_name,
        timezone=profile.timezone,
        model_choice=profile.model_choice or _models().default,
        connections=[
            s.Connection(
                platform=c.platform,
                status=c.status,
                expires_at=c.expires_at,
                last_sync_at=c.last_sync_at,
                last_error=c.last_error,
                account_label=c.account_label,
            )
            for c in rows
        ],
    )


@router.get("/me", response_model=s.Me)
async def get_me(user: User) -> s.Me:
    """DB mode: profile created with defaults on first call. Mock mode: the S02 demo student."""
    if _db_mode():
        return await _me_from_db(user)
    return s.Me(
        user_id=user.user_id,
        display_name="Demo Student",
        timezone=mock.TZ,
        model_choice="gemini/gemini-default",
        connections=mock.connections(),
    )


def _invalid(field: str, msg: str) -> AppError:
    return AppError("validation_error", msg, status=422)


@router.patch("/me", response_model=s.Me)
async def patch_me(body: s.MePatch, user: User) -> s.Me:
    """S20 rule 10: timezone must be an IANA name, model_choice one of /models (S26)."""
    if body.timezone is not None and body.timezone not in available_timezones():
        raise _invalid("timezone", "Pick a timezone from the list.")
    if body.model_choice is not None and body.model_choice not in {m.id for m in _models().models}:
        raise _invalid("model_choice", "Pick a model from the list.")
    if _db_mode():
        async with connection() as conn:
            await profiles.ensure_profile(conn, user.user_id, user.email)
            await profiles.update_profile(conn, user.user_id, **body.model_dump(exclude_none=True))
        return await _me_from_db(user)
    me = await get_me(user)
    return me.model_copy(update=body.model_dump(exclude_none=True))


@router.delete("/me/data", status_code=204)
async def delete_my_data(user: DeletionUser) -> Response:
    """Clear owned rows/files/jobs; Auth account remains. Retry safely after a partial failure."""
    if _db_mode():
        from app.db.deletion import clear_user_data

        async with connection() as conn:
            await clear_user_data(conn, user.user_id)
    return Response(status_code=204)


@router.get("/models", response_model=s.ModelsResponse)
async def list_models(user: User) -> s.ModelsResponse:
    return _models()


def _models() -> s.ModelsResponse:
    """Minimal S26 picker: Gemini is the default (decisions.md); availability = key configured."""
    settings = get_settings()
    return s.ModelsResponse(
        default="gemini/gemini-default",
        models=[
            s.ModelOption(
                id="gemini/gemini-default",
                label="Gemini (recommended)",
                provider="google",
                tier="recommended",
                available=bool(settings.gemini_api_key),
            ),
            s.ModelOption(
                id="openai/gpt-default",
                label="GPT",
                provider="openai",
                tier="recommended",
                available=bool(settings.openai_api_key),
            ),
            s.ModelOption(
                id="anthropic/claude-default",
                label="Claude",
                provider="anthropic",
                tier="recommended",
                available=False,
            ),
            s.ModelOption(
                id="ollama/llama-local",
                label="Local (Ollama)",
                provider="ollama",
                tier="experimental",
                available=False,
            ),
        ],
    )
