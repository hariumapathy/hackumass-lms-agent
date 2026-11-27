"""psycopg 3 async connection pool (S20). Opened lazily on first use; closed on app shutdown."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.errors import AppError
from app.core.settings import get_settings

_pool: AsyncConnectionPool[Any] | None = None


def db_unavailable() -> AppError:
    return AppError(
        "internal", "We can't reach your saved data right now. Try again.", 503, retryable=True
    )


async def get_pool() -> AsyncConnectionPool[Any]:
    global _pool
    if _pool is None:
        pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
        await pool.open(wait=False)
        _pool = pool
        return pool
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@dataclass
class _RequestConnection:
    conn: AsyncConnection[Any]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    owner: asyncio.Task[Any] | None = None
    active: bool = True


_request_connection: ContextVar[_RequestConnection | None] = ContextVar(
    "request_connection", default=None
)


@asynccontextmanager
async def bind_connection(conn: AsyncConnection[Any]) -> AsyncIterator[None]:
    """All request/tool leases use the guarded session; parallel tool transactions serialize."""
    scope = _RequestConnection(conn)
    token = _request_connection.set(scope)
    try:
        yield
    finally:
        scope.active = False

        async def drain() -> None:
            try:
                async with asyncio.timeout(5):
                    async with scope.lock:
                        pass
            except TimeoutError:
                await conn.close()  # stale child can never write via a recycled session
            except BaseException:
                await conn.close()
                raise

        cleanup = asyncio.create_task(drain())
        try:
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup  # finish fencing before the outer guard can unlock
                raise
        finally:
            _request_connection.reset(token)


def background_context():
    """An intentional background login owns a separate generation fence, not a request lease."""
    context = copy_context()
    context.run(_request_connection.set, None)
    return context


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    """Lease the request's guarded connection, or a fresh pooled connection outside requests."""
    try:
        scope = _request_connection.get()
        if scope is not None:
            if not scope.active:
                raise AppError(
                    "internal", "This request has finished. Try again.", 503, retryable=True
                )
            task = asyncio.current_task()
            if scope.owner is task:
                yield scope.conn  # same-task nested repository leases are safe
            else:
                async with scope.lock:
                    if not scope.active:
                        raise AppError(
                            "internal", "This request has finished. Try again.", 503, retryable=True
                        )
                    scope.owner = task
                    try:
                        yield scope.conn
                    finally:
                        scope.owner = None
            return
        pool = await get_pool()
        async with pool.connection(timeout=5) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        raise db_unavailable() from exc
