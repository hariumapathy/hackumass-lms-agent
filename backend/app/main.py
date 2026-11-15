"""FastAPI application entry point. Run with `make api`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.db_store import DbChatStore
from app.agent.runtime import ChatRuntime, agent_available, model_for
from app.agent.store import MemoryChatStore
from app.agent.tools.db_source import DbToolData
from app.agent.tools.mock_source import MockToolData
from app.api.routes import api_router
from app.core.auth import UserCtx
from app.core.clock import Clock, SystemClock
from app.core.embeddings import EmbeddingProvider, EmbeddingsConfigError, get_embeddings
from app.core.errors import install_error_handlers
from app.core.logging import RequestLogMiddleware, protect_calendar_access_logs
from app.core.ratelimit import TokenBucket
from app.core.settings import Settings, get_settings
from app.db.pool import close_pool, connection
from app.db.repositories import profiles

CHAT_REQUESTS_PER_MINUTE = 10
log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """In db mode, open the job queue so `fetch_latest` can enqueue syncs (S10)."""
    queue = None
    if get_settings().data_source == "db":
        try:
            from app.sync.jobs import app as queue_app

            await queue_app.open_async()
            queue = queue_app
        except Exception as exc:  # noqa: BLE001 - chat still works; fetch_latest reports failure
            log.warning("job queue unavailable: %s", type(exc).__name__)
    yield
    if queue is not None:
        await queue.close_async()
    await close_pool()


def default_chat_runtime(settings: Settings, clock: Clock) -> ChatRuntime | None:
    """Real agent unless CHAT_MODE=scripted or (auto and no model key). Tool data is the mock
    semester until S01/S03 land (then DbToolData scoped to the user)."""
    if settings.chat_mode == "scripted":
        return None
    if settings.chat_mode == "auto" and not agent_available(settings):
        return None
    if settings.data_source == "db":
        return ChatRuntime(
            store=DbChatStore(connection),
            data_factory=lambda user: DbToolData(
                user.user_id, connection, embedder=_embedder(settings)
            ),
            model_factory=lambda choice: model_for(choice, settings),
            clock=clock,
            profile_loader=_load_profile,
        )
    return ChatRuntime(
        store=MemoryChatStore(),
        data_factory=lambda _user: MockToolData(),
        model_factory=lambda choice: model_for(choice, settings),
        clock=clock,
    )


async def _load_profile(user: UserCtx) -> tuple[str, str | None]:
    async with connection() as conn:
        profile = await profiles.ensure_profile(conn, user.user_id, user.email)
    return profile.timezone, profile.model_choice


def _embedder(settings: Settings) -> EmbeddingProvider | None:
    try:
        return get_embeddings(settings)
    except EmbeddingsConfigError:
        return None  # search falls back to full-text only


def create_app(clock: Clock | None = None) -> FastAPI:
    protect_calendar_access_logs()
    settings = get_settings()
    clock = clock or SystemClock()
    app = FastAPI(title="HackUMass LMS Agent API", version="0.1.0", lifespan=_lifespan)
    app.state.clock = clock
    app.state.chat_runtime = default_chat_runtime(settings, clock)
    app.state.chat_limiter = TokenBucket(
        capacity=CHAT_REQUESTS_PER_MINUTE, per_seconds=60, clock=clock
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLogMiddleware)  # outermost: logs every request, incl. CORS/401s
    install_error_handlers(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
