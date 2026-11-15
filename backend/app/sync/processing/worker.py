"""Worker glue for the `process_material` / `process_post` jobs: credentials, storage, embeddings.

Only the worker decrypts secrets. Canvas downloads use `Authorization: Bearer <token>`; other
platforms' files are handled by their connectors (transcripts arrive as cues, no download).
"""

import logging
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from app.core.crypto import decrypt, get_fernet
from app.core.embeddings import get_embeddings
from app.db.repositories import sync as repo
from app.sync.processing.process import MaterialSource, process_material, process_post
from app.sync.processing.storage import StorageError, get_storage, http_downloader

log = logging.getLogger("app.sync.processing")


async def run_process_material(
    conn: AsyncConnection[Any], user_id: UUID, material_id: UUID, source: dict[str, Any] | None
) -> str:
    cur = await conn.execute(
        "select platform from materials where user_id = %s and id = %s", (user_id, material_id)
    )
    row = await cur.fetchone()
    if row is None:
        return "missing"
    src = MaterialSource.model_validate(source or {})
    token = None
    if src.download is not None and row["platform"] == "canvas":
        ciphertext = await repo.get_secret(conn, user_id, "canvas")
        token = decrypt(ciphertext, get_fernet()) if ciphertext else None
    try:
        storage = get_storage()
    except StorageError:
        log.warning("process_material: no service key; original file not stored")
        storage = None
    return await process_material(
        conn,
        user_id,
        material_id,
        source=src,
        embeddings=get_embeddings(),
        downloader=http_downloader(token),
        storage=storage,
    )


async def run_process_post(conn: AsyncConnection[Any], user_id: UUID, post_id: UUID) -> str:
    return await process_post(conn, user_id, post_id, embeddings=get_embeddings())
