"""FastAPI application entry point. Run with `make api`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.clock import Clock, SystemClock
from app.core.errors import install_error_handlers
from app.core.logging import RequestLogMiddleware
from app.core.ratelimit import TokenBucket
from app.core.settings import get_settings
from app.db.pool import close_pool

CHAT_REQUESTS_PER_MINUTE = 10


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_pool()


def create_app(clock: Clock | None = None) -> FastAPI:
    settings = get_settings()
    clock = clock or SystemClock()
    app = FastAPI(title="HackUMass LMS Agent API", version="0.1.0", lifespan=_lifespan)
    app.state.clock = clock
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
