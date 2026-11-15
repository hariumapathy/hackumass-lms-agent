"""S25: actual local Postgres, parsed ICS, no external calendar calls."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from icalendar import Calendar

from app.api.schemas import StudyBlock
from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.pool import close_pool
from app.db.repositories import calendar as calendar_repo
from app.main import create_app
from tests.helpers import auth_header
from tests.integration.db import (
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)


async def test_S25_T01_T03_database_proposals_scope_and_overlap(calendar_db):
    conn, users, rows, _ = calendar_db
    start = NOW + timedelta(days=3)
    block = StudyBlock(
        id=uuid4(),
        title="Study",
        start_at=start,
        end_at=start + timedelta(hours=1),
        course_id=rows[0]["courses"],
        item_id=rows[0]["items"],
        status="proposed",
    )
    assert await calendar_repo.propose(conn, users[0], block, NOW)
    assert not await calendar_repo.propose(
        conn, users[0], block.model_copy(update={"id": uuid4()}), NOW
    )
    with pytest.raises(ValueError, match="Course not found"):
        await calendar_repo.propose(conn, users[1], block, NOW)
    with pytest.raises(ValueError, match="Assignment not found"):
        await calendar_repo.propose(
            conn, users[1], block.model_copy(update={"course_id": None}), NOW
        )


@pytest.fixture
async def calendar_db(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    async for conn in conn_fixture():
        users = [await create_auth_user(conn) for _ in range(2)]
        rows = [await insert_minimal_rows(conn, u) for u in users]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(clock=FixedClock(NOW))),
            base_url="http://test",
        ) as client:
            try:
                yield conn, users, rows, client
            finally:
                await close_pool()
                for u in users:
                    await delete_auth_user(conn, u)


async def test_S25_T04_T05_T07_T08_feed_decisions_rotation(calendar_db):
    conn, users, rows, client = calendar_db
    u = users[0]
    h = auth_header(u)
    await conn.execute("update items set due_at=%s where user_id=%s", (NOW + timedelta(days=1), u))
    await conn.execute(
        "update study_blocks set start_at=%s,end_at=%s,created_at=%s where user_id=%s",
        (NOW + timedelta(hours=1), NOW + timedelta(hours=2), NOW, u),
    )
    first = await client.get("/calendar/feed", headers=h)
    assert first.status_code == 200
    url = first.json()["url"]
    path = "/calendar/" + url.rsplit("/", 1)[1]
    assert "demo-token" not in url
    assert (await client.get("/calendar/feed", headers=h)).json()["url"] == url
    response = await client.get(path)
    assert response.headers["cache-control"] == "max-age=900"
    events = Calendar.from_ical(response.content).walk("VEVENT")
    assert len(events) == 1
    assert events[0].decoded("dtend") - events[0].decoded("dtstart") == timedelta(minutes=15)
    assert str(events[0]["url"]) == "https://example.instructure.com/x"
    decision = await client.post(
        "/study-blocks/decision",
        headers=h,
        json={"block_ids": [str(r["study_blocks"]) for r in rows], "approve": True},
    )
    assert decision.status_code == 200 and len(decision.json()["blocks"]) == 1
    assert decision.json()["blocks"][0]["status"] == "approved"
    again = await client.post(
        "/study-blocks/decision",
        headers=h,
        json={"block_ids": [str(rows[0]["study_blocks"])], "approve": False},
    )
    assert again.json()["blocks"][0]["status"] == "approved"
    assert len(Calendar.from_ical((await client.get(path)).content).walk("VEVENT")) == 2
    cur = await conn.execute(
        "select status from study_blocks where id=%s", (rows[1]["study_blocks"],)
    )
    assert (await cur.fetchone())["status"] == "proposed"
    rotated = (await client.post("/calendar/feed/rotate", headers=h)).json()["url"]
    assert rotated != url and (await client.get(path)).status_code == 404
    assert (await client.get("/calendar/not-a-real-token.ics")).status_code == 404


async def test_S25_T06_stable_uid_sequence_and_escaping(calendar_db):
    conn, users, rows, client = calendar_db
    u = users[0]
    await conn.execute(
        "update items set title=%s,due_at=%s,updated_at=%s where user_id=%s",
        ("HW, one; two\nBEGIN:VEVENT", NOW + timedelta(days=2), NOW, u),
    )
    url = (await client.get("/calendar/feed", headers=auth_header(u))).json()["url"]
    path = "/calendar/" + url.rsplit("/", 1)[1]
    before = Calendar.from_ical((await client.get(path)).content).walk("VEVENT")[0]
    await conn.execute(
        "insert into changes (user_id,entity_type,entity_id,course_id,field) values "
        "(%s,'item',%s,%s,'due_at')",
        (u, rows[0]["items"], rows[0]["courses"]),
    )
    await conn.execute("update items set due_at=due_at+interval '1 day' where user_id=%s", (u,))
    events = Calendar.from_ical((await client.get(path)).content).walk("VEVENT")
    assert len(events) == 1 and events[0]["uid"] == before["uid"]
    assert int(str(events[0]["sequence"])) == int(str(before["sequence"])) + 1
    assert events[0].decoded("dtend") != before.decoded("dtend")


async def test_S25_T04_old_proposals_decline_removed_items_excluded(calendar_db):
    conn, users, rows, client = calendar_db
    u = users[0]
    await conn.execute(
        "update study_blocks set created_at=%s where user_id=%s", (NOW - timedelta(days=2), u)
    )
    response = await client.post(
        "/study-blocks/decision",
        headers=auth_header(u),
        json={"block_ids": [str(rows[0]["study_blocks"])], "approve": True},
    )
    assert response.json()["blocks"][0]["status"] == "declined"
    await conn.execute(
        "update items set status='removed',due_at=%s where user_id=%s", (NOW + timedelta(days=1), u)
    )
    url = (await client.get("/calendar/feed", headers=auth_header(u))).json()["url"]
    assert (
        Calendar.from_ical((await client.get("/calendar/" + url.rsplit("/", 1)[1])).content).walk(
            "VEVENT"
        )
        == []
    )
