# pyright: reportArgumentType=false, reportIndexIssue=false, reportOptionalSubscript=false
"""S12 file processing against the local DB (fake embeddings, fake downloader/storage)."""

from typing import Any
from uuid import UUID, uuid4

import httpx
import pymupdf
import pytest

from app.connectors.base import AuthExpired, DownloadRef, TranscriptCue
from app.core.embeddings import FakeEmbeddings
from app.core.settings import get_settings
from app.db.repositories import sync as repo
from app.sync.processing import (
    MaterialSource,
    SupabaseStorage,
    delete_user_files,
    process_material,
    process_post,
)
from app.sync.processing.failures import ProcessingFailure
from tests.integration.db import conn_fixture, create_auth_user, delete_auth_user

pytestmark = pytest.mark.integration
PDF = "application/pdf"


def make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.files[path] = data

    async def delete_prefix(self, prefix: str) -> int:
        gone = [p for p in self.files if p.startswith(prefix + "/")]
        for p in gone:
            del self.files[p]
        return len(gone)


class FailingEmbeddings(FakeEmbeddings):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise httpx.HTTPStatusError(
            "boom", request=httpx.Request("POST", "http://x"), response=httpx.Response(500)
        )


def downloader(data: bytes | Exception):  # noqa: ANN201
    async def dl(ref: DownloadRef) -> bytes:
        if isinstance(data, Exception):
            raise data
        return data

    return dl


@pytest.fixture
async def conn():  # noqa: ANN201
    async for c in conn_fixture():
        yield c


@pytest.fixture
async def user(conn) -> Any:  # noqa: ANN001
    uid = await create_auth_user(conn)
    yield uid
    await delete_auth_user(conn, uid)


async def setup_course(conn, user: UUID) -> UUID:  # noqa: ANN001
    cur = await conn.execute(
        "insert into courses (user_id, name, code) values (%s, 'Algorithms', 'COMPSCI 311') "
        "returning id",
        (user,),
    )
    cid = (await cur.fetchone())["id"]
    await conn.execute(
        "insert into course_links (user_id, course_id, platform, platform_id, source_url, "
        "content_hash) values (%s, %s, 'canvas', '12345', 'https://example.edu/c', 'h')",
        (user, cid),
    )
    return cid


async def add_material(conn, user: UUID, cid: UUID, **kw: Any) -> UUID:  # noqa: ANN001
    cur = await conn.execute(
        "insert into materials (user_id, course_id, kind, title, mime_type, platform, "
        "platform_id, source_url, content_hash) values (%s, %s, %s, %s, %s, 'canvas', %s, "
        "'https://example.edu/f', 'h') returning id",
        (
            user,
            cid,
            kw.get("kind", "file"),
            kw.get("title", "Lecture 7 slides"),
            kw.get("mime", PDF),
            kw.get("pid", "f7"),
        ),
    )
    return (await cur.fetchone())["id"]


async def chunks(conn, mid: UUID, col: str = "material_id") -> list[dict]:  # noqa: ANN001
    cur = await conn.execute(
        f"select text, page, start_s, end_s, material_version, is_current, token_count "
        f"from chunks where {col} = %s order by id",
        (mid,),
    )
    return await cur.fetchall()


async def material_row(conn, mid: UUID) -> dict:  # noqa: ANN001
    cur = await conn.execute(
        "select version, storage_path, page_count, duration_s, processing_status, "
        "processing_error from materials where id = %s",
        (mid,),
    )
    return await cur.fetchone()


def pdf_source() -> MaterialSource:
    return MaterialSource(download=DownloadRef(url="https://x/files/7", filename="Lecture7.pdf"))


async def run(conn, user, mid, data, storage=None, emb=None, source=None) -> str:  # noqa: ANN001
    return await process_material(
        conn,
        user,
        mid,
        source=source or pdf_source(),
        embeddings=emb or FakeEmbeddings(),
        downloader=downloader(data),
        storage=storage if storage is not None else FakeStorage(),
    )


# --- S12-T09 ----------------------------------------------------------------------------------
async def test_s12_t09_new_version_flips_old_chunks_atomically(conn, user) -> None:  # noqa: ANN001
    cid = await setup_course(conn, user)
    mid = await add_material(conn, user, cid)
    storage = FakeStorage()

    assert await run(conn, user, mid, make_pdf(["Memoization basics", "Greedy"]), storage) == "done"
    v1 = await chunks(conn, mid)
    assert [(c["page"], c["material_version"], c["is_current"]) for c in v1] == [
        (1, 1, True),
        (2, 1, True),
    ]
    assert v1[0]["text"] == "[COMPSCI 311 · Lecture 7 slides · p.1]\nMemoization basics"
    m = await material_row(conn, mid)
    assert (m["version"], m["page_count"], m["processing_status"]) == (1, 2, "done")
    assert m["storage_path"].startswith(f"users/{user}/canvas/12345/f7/v1-")
    assert m["storage_path"].endswith(".pdf")
    assert set(storage.files) == {m["storage_path"]}

    # Same content again: nothing new (no version bump, no new chunks).
    assert await run(conn, user, mid, make_pdf(["Memoization basics", "Greedy"]), storage) == (
        "unchanged"
    )
    assert len(await chunks(conn, mid)) == 2 and (await material_row(conn, mid))["version"] == 1

    # Changed file -> v2 current, v1 non-current, both files stored.
    new_pdf = make_pdf(["Memoization revised", "Greedy", "Dijkstra"])
    assert await run(conn, user, mid, new_pdf, storage) == "done"
    rows = await chunks(conn, mid)
    current = [r for r in rows if r["is_current"]]
    assert [r["material_version"] for r in current] == [2, 2, 2]
    assert all(not r["is_current"] for r in rows if r["material_version"] == 1)
    m = await material_row(conn, mid)
    assert (m["version"], m["page_count"]) == (2, 3)
    assert "/v2-" in m["storage_path"] and m["storage_path"].endswith(".pdf")
    assert len(storage.files) == 2

    # Embedding failure mid-update: v2 stays current, status failed, no partial v3.
    bad = make_pdf(["Totally new"])
    with pytest.raises(ProcessingFailure) as error:
        await run(conn, user, mid, bad, storage, emb=FailingEmbeddings())
    assert error.value.kind == "retry"
    rows = await chunks(conn, mid)
    assert [r["material_version"] for r in rows if r["is_current"]] == [2, 2, 2]
    assert not any(r["material_version"] == 3 for r in rows)
    assert (await material_row(conn, mid))["processing_status"] == "failed"


async def test_s12_scanned_pdf_skipped_and_corrupt_failed(conn, user) -> None:  # noqa: ANN001
    cid = await setup_course(conn, user)
    blank = pymupdf.open()
    blank.new_page()
    mid = await add_material(conn, user, cid)
    assert await run(conn, user, mid, blank.tobytes()) == "skipped"
    m = await material_row(conn, mid)
    assert m["processing_status"] == "skipped"
    assert m["processing_error"] == "no text; OCR out of scope"
    mid2 = await add_material(conn, user, cid, pid="f8")
    with pytest.raises(ProcessingFailure) as error:
        await run(conn, user, mid2, b"not a pdf")
    assert error.value.kind == "permanent"
    assert (await material_row(conn, mid2))["processing_status"] == "failed"
    assert await chunks(conn, mid) == [] and await chunks(conn, mid2) == []


async def test_s12_download_401_marks_connection_needs_reconnect(conn, user) -> None:  # noqa: ANN001
    cid = await setup_course(conn, user)
    await repo.upsert_connection_secret(conn, user, "canvas", b"ct", "canvas_token")
    mid = await add_material(conn, user, cid)
    assert await run(conn, user, mid, AuthExpired("401")) == "needs_reconnect"
    connection = await repo.get_connection(conn, user, "canvas")
    assert connection and connection.status == "needs_reconnect"
    assert (await material_row(conn, mid))["processing_status"] == "failed"


async def test_s12_transcript_and_inline_page(conn, user) -> None:  # noqa: ANN001
    cid = await setup_course(conn, user)
    tid = await add_material(conn, user, cid, kind="transcript", title="Lecture 7", mime=None)
    cues = [TranscriptCue(start_s=s, end_s=s + 30, text=f"Part {s}.") for s in range(0, 150, 30)]
    assert await run(conn, user, tid, b"", source=MaterialSource(cues=cues)) == "done"
    rows = await chunks(conn, tid)
    assert [(r["start_s"], r["end_s"]) for r in rows] == [(0, 60), (60, 120), (120, 150)]
    assert rows[1]["text"].startswith("[COMPSCI 311 · Lecture 7 · 1:00]\n")
    assert (await material_row(conn, tid))["duration_s"] == 150

    pid = await add_material(conn, user, cid, kind="page", title="Syllabus", mime=None, pid="p1")
    html = "<h2>Grading</h2><p>Exams 60%.</p>"
    assert await run(conn, user, pid, b"", source=MaterialSource(text=html)) == "done"
    [row] = await chunks(conn, pid)
    assert row["text"] == "[COMPSCI 311 · Syllabus]\nGrading\nExams 60%."
    assert (await material_row(conn, pid))["storage_path"] is None  # no file to store


async def test_s12_process_post_chunks_and_versions(conn, user) -> None:  # noqa: ANN001
    cid = await setup_course(conn, user)
    cur = await conn.execute(
        "insert into posts (user_id, course_id, kind, title, body, posted_at, platform, "
        "platform_id, source_url, content_hash) values (%s, %s, 'announcement', 'Exam moved', "
        "'<p>Midterm is now <b>Thursday</b>.</p>', now(), 'canvas', 'a1', 'https://x', 'h') "
        "returning id",
        (user, cid),
    )
    post_id = (await cur.fetchone())["id"]
    emb = FakeEmbeddings()
    assert await process_post(conn, user, post_id, embeddings=emb) == "done"
    [row] = await chunks(conn, post_id, "post_id")
    assert row["text"] == (
        "[COMPSCI 311 · Announcement · Exam moved]\nExam moved\nMidterm is now Thursday."
    )
    assert await process_post(conn, user, post_id, embeddings=emb) == "unchanged"
    await conn.execute("update posts set body = 'Midterm is Friday.' where id = %s", (post_id,))
    assert await process_post(conn, user, post_id, embeddings=emb) == "done"
    rows = await chunks(conn, post_id, "post_id")
    assert [r["is_current"] for r in rows] == [False, True]


# --- live local Storage (skips when the stack's Storage API isn't reachable) -------------------
async def test_s12_supabase_storage_roundtrip_and_delete_user_files() -> None:
    settings = get_settings()
    key = settings.supabase_service_role_key
    if key is None or not key.get_secret_value():
        pytest.skip("no SUPABASE_SERVICE_ROLE_KEY")
    if "127.0.0.1" not in settings.supabase_url and "localhost" not in settings.supabase_url:
        pytest.skip("only runs against the local Supabase stack")
    storage = SupabaseStorage(settings.supabase_url, key.get_secret_value())
    uid = uuid4()
    try:
        await storage.upload(f"users/{uid}/canvas/1/f1/v1.pdf", b"one", PDF)
        await storage.upload(f"users/{uid}/canvas/1/f1/v2.pdf", b"two", PDF)
        await storage.upload(f"users/{uid}/canvas/2/f9/v1.txt", b"three", "text/plain")
    except httpx.ConnectError:
        pytest.skip("local Storage API not running")
    other = uuid4()
    await storage.upload(f"users/{other}/canvas/1/f1/v1.pdf", b"keep", PDF)
    try:
        assert await delete_user_files(uid, storage) == 3
        assert await storage.delete_prefix(f"users/{uid}") == 0
    finally:
        assert await storage.delete_prefix(f"users/{other}") == 1
