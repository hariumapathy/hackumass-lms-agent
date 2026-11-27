"""process_material / process_post (S12): download -> store original -> extract -> chunk -> embed
-> write chunks. New chunks are inserted and the previous version's chunks flipped to
`is_current=false` in one transaction, so search never sees a half-updated material (rule 6).

Runs on an autocommit `dict_row` connection (the worker's). Every query filters by `user_id`.
"""

import logging
import mimetypes
from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from pydantic import BaseModel

from app.connectors.base import AuthExpired, DownloadRef, NMaterial, SourceSuperseded, TranscriptCue
from app.core.embeddings import BATCH_SIZE, EmbeddingProvider, to_pgvector
from app.db.repositories import sync as repo
from app.sync.access import require_current
from app.sync.access import snapshot as connection_snapshot
from app.sync.processing.chunker import ChunkDraft, chunk
from app.sync.processing.extract import (
    EXTENSIONS,
    NO_TEXT,
    ExtractError,
    SkipProcessing,
    Unit,
    extract,
    extract_transcript,
    html_to_text,
    looks_like_html,
)
from app.sync.processing.failures import classify
from app.sync.processing.publication import (
    ProcessingSuperseded,
    WorkSnapshot,
    complete,
    parent_work,
    publication,
    snapshot,
)
from app.sync.processing.storage import Downloader, Storage, storage_path

log = logging.getLogger("app.sync.processing")

POST_LABEL = {"announcement": "Announcement", "piazza": "Piazza", "email": "Email"}
RECONNECT_MSG = "Your sign-in for this site expired."


class MaterialSource(BaseModel):
    """What the connector gave us besides the DB row (it isn't stored in `materials`)."""

    download: DownloadRef | None = None
    text: str | None = None
    cues: list[TranscriptCue] | None = None

    @classmethod
    def from_record(cls, rec: NMaterial) -> "MaterialSource":
        return cls(download=rec.download, text=rec.text, cues=rec.cues)


async def _one(conn: AsyncConnection[Any], sql: str, params: tuple[Any, ...]) -> Any:
    cur = await conn.execute(sql, params)  # type: ignore[arg-type]
    return await cur.fetchone()


async def _set_status(
    conn: AsyncConnection[Any],
    work: WorkSnapshot,
    status: str,
    error: str | None,
    *,
    finished: bool = False,
) -> None:
    async with publication(conn, work):
        await conn.execute(
            "update materials set processing_status=%s,processing_error=%s "
            "where user_id=%s and id=%s",
            (status, error[:500] if error else None, work.user_id, work.parent_id),
        )
        if finished:
            await complete(conn, work)


def _mime(mime_type: str | None, filename: str | None) -> str | None:
    if mime_type and mime_type != "application/octet-stream":
        return mime_type
    if filename:
        return mimetypes.guess_type(filename)[0] or mime_type
    return mime_type


def _ext(mime: str | None, filename: str | None) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[1].lower()[:10]
    return EXTENSIONS.get((mime or "").split(";")[0], "bin")


async def _current_texts(conn: AsyncConnection[Any], user_id: UUID, col: str, parent: UUID) -> list:
    cur = await conn.execute(
        f"select text from chunks where user_id = %s and {col} = %s and is_current "  # type: ignore[arg-type]  # noqa: S608
        "order by id",
        (user_id, parent),
    )
    return [r["text"] for r in await cur.fetchall()]


async def _embed(embeddings: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):  # rule 7: batches of 100
        out.extend(await embeddings.embed(texts[i : i + BATCH_SIZE]))
    return out


async def _write_chunks(
    conn: AsyncConnection[Any],
    user_id: UUID,
    course_id: UUID,
    drafts: list[ChunkDraft],
    vectors: list[list[float]],
    *,
    material_id: UUID | None = None,
    post_id: UUID | None = None,
    version: int | None = None,
) -> list[int]:
    """Insert new current chunks, then flip every other current chunk of the parent. Call inside
    a transaction."""
    new_ids: list[int] = []
    for d, vec in zip(drafts, vectors, strict=True):
        row = await _one(
            conn,
            "insert into chunks (user_id, course_id, material_id, post_id, material_version, "
            "is_current, text, page, start_s, end_s, token_count, embedding) "
            "values (%s,%s,%s,%s,%s,true,%s,%s,%s,%s,%s,%s::extensions.vector) returning id",
            (
                user_id,
                course_id,
                material_id,
                post_id,
                version,
                d.text,
                d.page,
                d.start_s,
                d.end_s,
                d.token_count,
                to_pgvector(vec),
            ),
        )
        new_ids.append(row["id"])
    col, parent = ("material_id", material_id) if material_id else ("post_id", post_id)
    await conn.execute(
        f"update chunks set is_current = false where user_id = %s and {col} = %s "  # noqa: S608
        "and is_current and not (id = any(%s))",
        (user_id, parent, new_ids),
    )
    return new_ids


async def process_material(
    conn: AsyncConnection[Any],
    user_id: UUID,
    material_id: UUID,
    *,
    source: MaterialSource | None,
    embeddings: EmbeddingProvider,
    downloader: Downloader | None = None,
    storage: Storage | None = None,
) -> str:
    """Trusted processor helper; all paths capture/fence source state, including legacy fixtures."""
    async with parent_work(conn, user_id, material_id, "materials"):
        try:
            return await _process_material(
                conn,
                user_id,
                material_id,
                source=source,
                embeddings=embeddings,
                downloader=downloader,
                storage=storage,
            )
        except (ProcessingSuperseded, SourceSuperseded):
            return "superseded"


async def _process_material(
    conn: AsyncConnection[Any],
    user_id: UUID,
    material_id: UUID,
    *,
    source: MaterialSource | None,
    embeddings: EmbeddingProvider,
    downloader: Downloader | None = None,
    storage: Storage | None = None,
) -> str:
    """Returns done | unchanged | skipped | needs_reconnect | missing.
    Raises safe classified failures; legacy workers retry only retryable PlatformErrors."""
    m = await _one(
        conn,
        "select m.id, m.course_id, m.kind, m.title, m.mime_type, m.storage_path, m.version, "
        "m.platform, m.platform_id, m.content_hash, m.source_revision, m.status, c.code, c.name, "
        "(select l.platform_id from course_links l where l.user_id = m.user_id "
        " and l.course_id = m.course_id and l.platform = m.platform limit 1) as course_pid "
        "from materials m join courses c on c.id = m.course_id and c.user_id=m.user_id "
        "where m.user_id = %s and m.id = %s",
        (user_id, material_id),
    )
    if m is None:
        return "missing"
    work = snapshot(user_id, material_id, "materials", m)
    source = source or MaterialSource()
    account_grant = None
    if source.download:
        try:
            account_grant = await connection_snapshot(conn, user_id, m["platform"])
        except SourceSuperseded:
            pass  # Trusted fixture helpers may use fake downloads without a connected platform.
    await _set_status(conn, work, "processing", None)
    try:
        data: bytes | None = None
        mime = m["mime_type"]
        if source.cues:
            ex = extract_transcript(source.cues)
        elif source.download is not None:
            if downloader is None:
                raise ExtractError("no downloader configured")
            data = await downloader(source.download)
            mime = _mime(mime, source.download.filename)
            ex = extract(mime, data)
        elif source.text and source.text.strip():
            text_mime = mime if mime and mime.startswith("text/") else None
            text_mime = text_mime or ("text/html" if looks_like_html(source.text) else "text/plain")
            ex = extract(text_mime, source.text.encode("utf-8"))
        else:
            raise SkipProcessing("nothing to process (no file, text or transcript)")

        drafts = chunk(ex.units, context=f"{m['code'] or m['name']} · {m['title']}")
        if not drafts:
            raise SkipProcessing(NO_TEXT)
        current = await _current_texts(conn, user_id, "material_id", material_id)
        if current == [d.text for d in drafts]:  # same content: no new version, no re-embedding
            await _set_status(conn, work, "done", None, finished=True)
            return "unchanged"

        version = m["version"] + 1 if (current or m["storage_path"]) else m["version"]
        vectors = await _embed(embeddings, [d.text for d in drafts])
        path = None
        if data is not None and storage is not None:
            async with publication(conn, work):
                pass  # Stop known-stale candidates before external upload; no I/O under row locks.
            path = storage_path(
                user_id,
                m["platform"],
                m["course_pid"] or str(m["course_id"]),
                m["platform_id"],
                version,
                _ext(mime, source.download.filename if source.download else None),
                attempt_id=uuid4(),
            )
            await storage.upload(path, data, mime or "application/octet-stream")
        async with publication(conn, work) as parent:
            # Same-parent processors serialize; still allocate from the locked current state.
            version = (
                parent["version"] + 1 if (current or parent["storage_path"]) else parent["version"]
            )
            await _write_chunks(
                conn,
                user_id,
                m["course_id"],
                drafts,
                vectors,
                material_id=material_id,
                version=version,
            )
            await conn.execute(
                "update materials set version=%s,storage_path=%s, "
                "page_count=%s,duration_s=%s, "
                "processing_status='done',processing_error=null where user_id=%s and id=%s",
                (version, path, ex.page_count, ex.duration_s, user_id, material_id),
            )
            await complete(conn, work)
        return "done"
    except ProcessingSuperseded:
        raise
    except SkipProcessing as exc:
        await _set_status(conn, work, "skipped", str(exc), finished=True)
        return "skipped"
    except AuthExpired:
        # Lock account first, matching source import/disconnect order. An old auth failure
        # must not poison a replacement connection; download grant fencing itself is S49.
        async with conn.transaction():
            if account_grant is not None:
                await require_current(
                    conn, user_id, m["platform"], account_grant, locked=True, update=True
                )
            async with publication(conn, work):
                if account_grant is not None:
                    await repo.set_connection_status(
                        conn, user_id, m["platform"], "needs_reconnect", error=RECONNECT_MSG
                    )
                await _set_status(conn, work, "failed", RECONNECT_MSG)
        return "needs_reconnect"
    except Exception as exc:
        failure = classify(exc)
        await _set_status(
            conn,
            work,
            "failed",
            "This file couldn't be prepared. Open the original course page for now.",
        )
        raise failure from None


async def process_post(
    conn: AsyncConnection[Any], user_id: UUID, post_id: UUID, *, embeddings: EmbeddingProvider
) -> str:
    async with parent_work(conn, user_id, post_id, "posts"):
        try:
            return await _process_post(conn, user_id, post_id, embeddings=embeddings)
        except ProcessingSuperseded:
            return "superseded"


async def _process_post(
    conn: AsyncConnection[Any], user_id: UUID, post_id: UUID, *, embeddings: EmbeddingProvider
) -> str:
    """One unit (title + body) -> chunk(s) with header `[CODE · Announcement · Title]` (same as the
    S03 seed). Returns done | unchanged | empty | missing."""
    p = await _one(
        conn,
        "select p.id, p.course_id, p.kind, p.title, p.body, p.status, p.source_revision, "
        "p.content_hash, c.code, c.name from posts p "
        "join courses c on c.id = p.course_id and c.user_id=p.user_id "
        "where p.user_id = %s and p.id = %s",
        (user_id, post_id),
    )
    if p is None:
        return "missing"
    work = snapshot(user_id, post_id, "posts", p)
    body = p["body"] or ""
    if looks_like_html(body):
        body = html_to_text(body)
    title = p["title"]
    label = POST_LABEL.get(p["kind"], "Post")
    drafts = chunk(
        [Unit(text=f"{title}\n{body}".strip())],
        context=f"{p['code'] or p['name']} · {label} · {title}",
    )
    if not drafts:
        async with publication(conn, work):
            await complete(conn, work)
        return "empty"
    if await _current_texts(conn, user_id, "post_id", post_id) == [d.text for d in drafts]:
        async with publication(conn, work):
            await complete(conn, work)
        return "unchanged"
    vectors = await _embed(embeddings, [d.text for d in drafts])
    async with publication(conn, work):
        await _write_chunks(conn, user_id, p["course_id"], drafts, vectors, post_id=post_id)
        await complete(conn, work)
    return "done"
