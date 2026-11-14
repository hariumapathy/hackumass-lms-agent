"""Account endpoints: /me, /me/data, /models (S02 stubs; real logic in S20, S26, S34)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api import mock_data as mock
from app.api import schemas as s
from app.api.deps import UserCtx, current_user

router = APIRouter(tags=["account"])
User = Annotated[UserCtx, Depends(current_user)]


@router.get("/me", response_model=s.Me)
async def get_me(user: User) -> s.Me:
    return s.Me(
        user_id=user.user_id,
        display_name="Demo Student",
        timezone=mock.TZ,
        model_choice="openai/gpt-default",
        connections=mock.connections(),
    )


@router.patch("/me", response_model=s.Me)
async def patch_me(body: s.MePatch, user: User) -> s.Me:
    me = await get_me(user)
    return me.model_copy(update=body.model_dump(exclude_none=True))


@router.delete("/me/data", status_code=204)
async def delete_my_data(user: User) -> Response:
    return Response(status_code=204)


@router.get("/models", response_model=s.ModelsResponse)
async def list_models(user: User) -> s.ModelsResponse:
    return s.ModelsResponse(
        default="openai/gpt-default",
        models=[
            s.ModelOption(
                id="openai/gpt-default",
                label="GPT (default)",
                provider="openai",
                tier="recommended",
                available=True,
            ),
            s.ModelOption(
                id="anthropic/claude-default",
                label="Claude",
                provider="anthropic",
                tier="recommended",
                available=False,
            ),
            s.ModelOption(
                id="gemini/gemini-default",
                label="Gemini",
                provider="google",
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
