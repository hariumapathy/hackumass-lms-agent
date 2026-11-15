"""In-app file viewer (split-2026-11-15 B2): `GET /files/{material_id}` streams the student's own
stored original; citations carry `file_id` only when there is a stored PDF to show."""

from datetime import UTC, datetime

import httpx
import pytest

from app.api.routes.files import file_storage
from app.core.clock import FixedClock
from app.core.settings import get_settings
from app.db.pool import close_pool
from app.main import create_app
from tests.helpers import auth_header
from tests.integration.db import (
    conn_fixture,
    create_auth_user,
    delete_auth_user,
    insert_minimal_rows,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
PDF = b"%PDF-1.4\n% fake pdf for tests\n"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.reads: list[str] = []

    async def download(self, path: str) -> bytes | None:
        self.reads.append(path)
        return self.objects.get(path)


@pytest.fixture
async def students():  # noqa: ANN201
    async for conn in conn_fixture():
        users = [await create_auth_user(conn) for _ in range(2)]
        rows = [await insert_minimal_rows(conn, uid) for uid in users]
        try:
            yield conn, users, rows
        finally:
            await close_pool()
            for uid in users:
                await delete_auth_user(conn, uid)


@pytest.fixture
async def env(monkeypatch):  # noqa: ANN001, ANN201
    monkeypatch.setenv("DATA_SOURCE", "db")
    get_settings.cache_clear()
    storage = FakeStorage()
    app = create_app(clock=FixedClock(NOW))
    app.dependency_overrides[file_storage] = lambda: storage
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, storage


async def _store_pdf(conn, uid, mid, storage: FakeStorage, mime="application/pdf") -> str:  # noqa: ANN001
    path = f"users/{uid}/canvas/c/{mid}/v1.pdf"
    storage.objects[path] = PDF
    await conn.execute(
        "update materials set storage_path = %s, mime_type = %s where user_id = %s and id = %s",
        (path, mime, uid, mid),
    )
    return path


async def test_files_streams_own_pdf_inline(students, env):  # noqa: ANN001, ANN201
    conn, users, rows = students
    client, storage = env
    uid, mid = users[0], rows[0]["materials"]
    await _store_pdf(conn, uid, mid, storage)
    res = await client.get(f"/files/{mid}", headers=auth_header(uid))
    assert res.status_code == 200, res.text
    assert res.content == PDF
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline")
    assert "private" in res.headers["cache-control"]


async def test_files_never_serves_another_students_file(students, env):  # noqa: ANN001, ANN201
    conn, users, rows = students
    client, storage = env
    other_mid = rows[1]["materials"]
    await _store_pdf(conn, users[1], other_mid, storage)
    res = await client.get(f"/files/{other_mid}", headers=auth_header(users[0]))
    assert res.status_code == 404
    assert storage.reads == []  # storage never touched for someone else's row
    assert (await client.get(f"/files/{other_mid}")).status_code == 401


async def test_files_missing_file_is_404(students, env):  # noqa: ANN001, ANN201
    conn, users, rows = students
    client, storage = env
    uid, mid = users[0], rows[0]["materials"]
    assert (await client.get(f"/files/{mid}", headers=auth_header(uid))).status_code == 404
    path = await _store_pdf(conn, uid, mid, storage)
    del storage.objects[path]  # row says stored, storage lost it
    assert (await client.get(f"/files/{mid}", headers=auth_header(uid))).status_code == 404


async def test_citations_file_id_only_for_stored_pdfs(students, env):  # noqa: ANN001, ANN201
    conn, users, rows = students
    client, storage = env
    uid, ids = users[0], rows[0]
    h = auth_header(uid)
    url = f"/citations?ids={ids['chunks']}"
    assert (await client.get(url, headers=h)).json()[0]["file_id"] is None
    await _store_pdf(conn, uid, ids["materials"], storage)
    assert (await client.get(url, headers=h)).json()[0]["file_id"] == str(ids["materials"])
    await _store_pdf(conn, uid, ids["materials"], storage, mime="application/vnd.ms-powerpoint")
    await conn.execute(
        "update materials set storage_path = replace(storage_path, '.pdf', '.pptx') "
        "where user_id = %s",
        (uid,),
    )
    assert (await client.get(url, headers=h)).json()[0]["file_id"] is None
