"""psycopg 3 async connection pool (S20). Opened lazily on first use; closed on app shutdown."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection]:
    """Yields a pooled connection; DB outages become a retryable 503 `internal` error."""
    try:
        pool = await get_pool()
        async with pool.connection(timeout=5) as conn:
            yield conn
    except psycopg.OperationalError as exc:  # includes PoolTimeout
        raise db_unavailable() from exc
