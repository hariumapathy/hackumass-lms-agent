"""S46-T07: connection fencing occurs before each external read, never after it."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import Field, SecretStr

from app.connectors.base import ConnectorContext, SyncScope
from app.connectors.canvas.client import CanvasClient, ForbiddenMethod
from app.connectors.canvas.connector import CanvasConnector
from app.core.clock import FixedClock
from tests.canvas_fake import API, BASE, mock_canvas
from tests.connector.test_s14_gradescope import ROUTES
from tests.connector.test_s14_gradescope import STATE as GS_STATE
from tests.connector.test_s14_gradescope import make_connector as gradescope_connector
from tests.piazza_fake import STATE as PIAZZA_STATE
from tests.piazza_fake import make_connector as piazza_connector


class Superseded(RuntimeError):
    """Synthetic guard rejection; must propagate without changing into auth/transient errors."""


class ReadGuard:
    def __init__(self, allowed: int) -> None:
        self.allowed = allowed
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1
        if self.calls > self.allowed:
            raise Superseded("Source access changed.")


class CheckedContext(ConnectorContext):
    """Exercise checkpoints before the shared base interface is added by the S46 owner."""

    check_current: Any = Field(default=None, exclude=True)

    async def checkpoint(self) -> None:
        if self.check_current:
            await self.check_current()


def context(platform: str, state: Any, guard: ReadGuard) -> CheckedContext:
    import json

    return CheckedContext(
        user_id=uuid4(),
        platform=platform,  # type: ignore[arg-type]
        secret=SecretStr(state if isinstance(state, str) else json.dumps(state)),
        clock=FixedClock(datetime(2026, 11, 14, 20, tzinfo=UTC)),
        check_current=guard,
    )


@pytest.mark.parametrize("validate,allowed", [(True, 0), (False, 0), (False, 1)])
async def test_s46_t07_canvas_connector_checks_before_reads(validate: bool, allowed: int) -> None:
    guard = ReadGuard(allowed)
    ctx = context("canvas", "fixture-token", guard)
    with respx.mock(assert_all_called=False) as router:
        mock_canvas(router)
        connector = CanvasConnector(BASE)
        with pytest.raises(Superseded):
            if validate:
                await connector.validate(ctx)
            else:
                _ = [record async for record in connector.fetch(ctx, SyncScope())]
        assert len(router.calls) == allowed
    assert guard.calls == allowed + 1


async def test_s46_t07_canvas_checks_next_page_and_preserves_get_only() -> None:
    guard = ReadGuard(1)
    with respx.mock(assert_all_called=False) as router:
        first = router.get(f"{API}/courses").respond(
            json=[1], headers={"Link": f'<{API}/courses?page=2>; rel="next"'}
        )
        async with httpx.AsyncClient() as http:
            client = CanvasClient(BASE, SecretStr("fixture-token"), http, checkpoint=guard)
            with pytest.raises(ForbiddenMethod):
                await client.request("POST", "/api/v1/courses")
            assert guard.calls == 0 and not first.called
            pages = client.paginate("/api/v1/courses")
            assert await anext(pages) == 1
            with pytest.raises(Superseded):
                await anext(pages)
        assert len(router.calls) == 1
    assert guard.calls == 2


@pytest.mark.parametrize("validate,allowed", [(True, 0), (False, 0), (False, 1), (False, 2)])
async def test_s46_t07_gradescope_checks_before_pages(validate: bool, allowed: int) -> None:
    guard = ReadGuard(allowed)
    connector, adapter = gradescope_connector(ROUTES)
    ctx = context("gradescope", GS_STATE, guard)
    with pytest.raises(Superseded):
        if validate:
            await connector.validate(ctx)
        else:
            _ = [record async for record in connector.fetch(ctx, SyncScope())]
    assert len(adapter.calls) == allowed
    assert guard.calls == allowed + 1


@pytest.mark.parametrize("validate,allowed", [(True, 0), (False, 0), (False, 1), (False, 2)])
async def test_s46_t07_piazza_checks_before_rpc(validate: bool, allowed: int) -> None:
    guard = ReadGuard(allowed)
    connector, adapter = piazza_connector()
    ctx = context("piazza", PIAZZA_STATE, guard)
    with pytest.raises(Superseded):
        if validate:
            await connector.validate(ctx)
        else:
            _ = [record async for record in connector.fetch(ctx, SyncScope())]
    assert len(adapter.calls) == allowed
    assert guard.calls == allowed + 1
