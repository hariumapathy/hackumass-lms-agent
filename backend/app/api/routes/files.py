"""In-app file viewer (split-2026-11-15 B2): stream a stored original to its owner.

The bytes come from the private `materials` bucket with the service key, so the route itself is
the access check: only a row of the signed-in student's own `materials` is ever read, and the
storage path comes from that row (never from the request).
"""

from typing import Annotated, Any, Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.api.deps import UserCtx, data_user
from app.core.errors import not_found
from app.core.settings import get_settings
from app.db.pool import connection

router = APIRouter(tags=["files"])
User = Annotated[UserCtx, Depends(data_user)]


class FileStorage(Protocol):
    async def download(self, path: str) -> bytes | None: ...


def file_storage() -> FileStorage:
    from app.sync.processing.storage import get_storage

    return get_storage()


def _content_type(mime: str | None, path: str) -> str:
    if mime and mime != "application/octet-stream":
        return mime
    return "application/pdf" if path.lower().endswith(".pdf") else "application/octet-stream"


@router.get(
    "/files/{material_id}",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The stored file"}},
)
async def get_file(
    material_id: UUID,
    user: User,
    storage: Annotated[FileStorage, Depends(file_storage)],
) -> Response:
    if get_settings().data_source != "db":
        raise not_found("File")
    async with connection() as conn:
        cur = await conn.execute(
            "select storage_path, mime_type from materials "
            "where user_id = %s and id = %s and status <> 'removed'",
            (user.user_id, material_id),
        )
        row = cast(dict[str, Any] | None, await cur.fetchone())
    if row is None or not row["storage_path"]:
        raise not_found("File")
    data = await storage.download(row["storage_path"])
    if data is None:
        raise not_found("File")
    return Response(
        content=data,
        media_type=_content_type(row["mime_type"], row["storage_path"]),
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
