"""S25 proposal validation: no live model or platform calls."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agent.store import MemoryChatStore
from app.agent.tools.context import RunCtx
from app.agent.tools.runner import ToolRejected
from app.agent.tools.study_blocks import AddStudyBlockArgs, add_study_block, local_start
from app.core.clock import FixedClock

NOW = datetime(2026, 10, 31, 16, tzinfo=UTC)


async def test_S25_T01_valid_proposal_is_proposed_and_persisted():
    store = MemoryChatStore()
    ctx = RunCtx(
        user_id=uuid4(), timezone="America/New_York", clock=FixedClock(NOW), block_store=store
    )
    result = await add_study_block(
        ctx,
        AddStudyBlockArgs(
            title="Exam review", start_local=datetime(2026, 11, 1, 10), duration_min=60
        ),
    )
    assert "awaiting" in result.results[0]["status"]
    assert len(ctx.proposed_blocks) == 1 and ctx.proposed_blocks[0].status == "proposed"
    assert (await store.blocks(ctx.user_id))[0].start_at == datetime(2026, 11, 1, 15, tzinfo=UTC)


@pytest.mark.parametrize("start", [datetime(2026, 10, 30, 12), datetime(2026, 12, 15, 12)])
async def test_S25_T02_invalid_dates_rejected(start):
    ctx = RunCtx(
        user_id=uuid4(),
        timezone="America/New_York",
        clock=FixedClock(NOW),
        block_store=MemoryChatStore(),
    )
    with pytest.raises(ToolRejected):
        await add_study_block(
            ctx, AddStudyBlockArgs(title="Study", start_local=start, duration_min=30)
        )


async def test_S25_T02_overlap_and_limit_rejected():
    ctx = RunCtx(
        user_id=uuid4(),
        timezone="America/New_York",
        clock=FixedClock(NOW),
        block_store=MemoryChatStore(),
    )
    args = AddStudyBlockArgs(title="Study", start_local=datetime(2026, 11, 1, 10), duration_min=30)
    await add_study_block(ctx, args)
    with pytest.raises(ToolRejected, match="overlap"):
        await add_study_block(ctx, args)
    ctx.proposed_blocks *= 10
    with pytest.raises(ToolRejected, match="10"):
        await add_study_block(ctx, args)


def test_S25_T03_dst_conversion_rejects_nonexistent_ambiguous():
    assert local_start(datetime(2026, 11, 1, 10), "America/New_York") == datetime(
        2026, 11, 1, 15, tzinfo=UTC
    )
    for time in [datetime(2026, 3, 8, 2, 30), datetime(2026, 11, 1, 1, 30)]:
        with pytest.raises(ToolRejected):
            local_start(time, "America/New_York")
