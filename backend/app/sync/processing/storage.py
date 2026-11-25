"""Original-file storage (Supabase Storage REST API, private bucket `materials`) and downloads.

Path layout (07, S12): `users/{user_id}/{platform}/{course_platform_id}/{platform_id}/v{n}.{ext}`.
`delete_user_files(user_id)` removes everything under `users/{user_id}/` (S20 "delete my data").
Worker-only: uses the service-role key, never exposed to clients.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.connectors.base import DownloadRef, PlatformError, SourceAccessError
from app.core.settings import Settings, get_settings
from app.sync.processing.extract import MAX_BYTES, ExtractError, SkipProcessing

BUCKET = "materials"
Downloader = Callable[[DownloadRef], Awaitable[bytes]]


def storage_path(
    user_id: object,
    platform: str,
    course_platform_id: str,
    platform_id: str,
    version: int,
    ext: str,
) -> str:
    safe = [quote(str(p), safe="-_.") for p in (course_platform_id, platform_id)]
    return f"users/{user_id}/{platform}/{safe[0]}/{safe[1]}/v{version}.{ext}"


class Storage(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    async def delete_prefix(self, prefix: str) -> int: ...


class StorageError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class SupabaseStorage:
    def __init__(
        self,
        url: str,
        service_key: str,
        bucket: str = BUCKET,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base = f"{url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self._client = client
        self.headers = {"apikey": service_key}
        if not service_key.startswith("sb_"):  # legacy JWT keys also go in Authorization
            self.headers["Authorization"] = f"Bearer {service_key}"

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = {**self.headers, **kw.pop("headers", {})}
        if self._client is not None:
            return await self._client.request(method, f"{self.base}{path}", headers=headers, **kw)
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.request(method, f"{self.base}{path}", headers=headers, **kw)

    @staticmethod
    def _bucket_missing(resp: httpx.Response) -> bool:
        return resp.status_code in {400, 404} and "bucket not found" in resp.text.lower()

    async def ensure_bucket(self) -> None:
        resp = await self._request(
            "POST", "/bucket", json={"id": self.bucket, "name": self.bucket, "public": False}
        )
        if resp.status_code >= 400 and "already exists" not in resp.text.lower():
            raise StorageError("could not create bucket", status_code=resp.status_code)

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        for attempt in range(2):
            resp = await self._request(
                "POST",
                f"/object/{self.bucket}/{path}",
                content=data,
                headers={"Content-Type": content_type, "x-upsert": "true"},
            )
            if attempt == 0 and self._bucket_missing(resp):
                await self.ensure_bucket()
                continue
            if resp.status_code >= 400:
                raise StorageError("upload failed", status_code=resp.status_code)
            return

    async def download(self, path: str) -> bytes | None:
        """One stored object (API file viewer). Missing object or bucket -> None."""
        resp = await self._request("GET", f"/object/{self.bucket}/{path}")
        if resp.status_code in {400, 404}:
            return None
        if resp.status_code >= 400:
            raise StorageError("download failed", status_code=resp.status_code)
        return resp.content

    async def _list(self, prefix: str) -> list[str]:
        """All object paths under `prefix` (the list endpoint is one level deep; recurse)."""
        out: list[str] = []
        offset = 0
        while True:
            resp = await self._request(
                "POST",
                f"/object/list/{self.bucket}",
                json={"prefix": prefix, "limit": 1000, "offset": offset},
            )
            if self._bucket_missing(resp):
                return []
            if resp.status_code >= 400:
                raise StorageError("list failed", status_code=resp.status_code)
            entries = resp.json()
            for e in entries:
                full = f"{prefix.rstrip('/')}/{e['name']}"
                if e.get("id") is None:  # folder
                    out.extend(await self._list(full))
                else:
                    out.append(full)
            if len(entries) < 1000:
                return out
            offset += 1000

    async def delete_prefix(self, prefix: str) -> int:
        paths = await self._list(prefix)
        for i in range(0, len(paths), 1000):
            resp = await self._request(
                "DELETE", f"/object/{self.bucket}", json={"prefixes": paths[i : i + 1000]}
            )
            if resp.status_code >= 400:
                raise StorageError("delete failed", status_code=resp.status_code)
        return len(paths)


def get_storage(settings: Settings | None = None) -> SupabaseStorage:
    settings = settings or get_settings()
    key = settings.supabase_service_role_key
    if key is None or not key.get_secret_value():
        raise StorageError("SUPABASE_SERVICE_ROLE_KEY is not set; file storage is unavailable.")
    return SupabaseStorage(settings.supabase_url, key.get_secret_value())


async def delete_user_files(user_id: object, storage: Storage | None = None) -> int:
    """Delete every stored file under `users/{user_id}/`. Returns the number of objects removed."""
    return await (storage or get_storage()).delete_prefix(f"users/{user_id}")


def http_downloader(
    bearer_token: str | None, client: httpx.AsyncClient | None = None
) -> Downloader:
    """Download with the worker's credentials. httpx drops `Authorization` on cross-origin
    redirects (Canvas file downloads redirect to a signed S3/CDN URL)."""

    async def download(ref: DownloadRef) -> bytes:
        if ref.size_bytes is not None and ref.size_bytes > MAX_BYTES:
            raise SkipProcessing("file is over 50 MB")
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        own = client is None
        c = client or httpx.AsyncClient(timeout=60, follow_redirects=True)
        try:
            async with c.stream("GET", ref.url, headers=headers, follow_redirects=True) as resp:
                if resp.status_code in {401, 403}:
                    raise SourceAccessError("This file is unavailable.")
                if resp.status_code in {408, 409, 425, 429} or resp.status_code >= 500:
                    raise PlatformError(f"download failed: {resp.status_code}")
                if resp.status_code >= 400:
                    raise ExtractError(f"download failed: {resp.status_code}")
                if int(resp.headers.get("content-length") or 0) > MAX_BYTES:
                    raise SkipProcessing("file is over 50 MB")
                buf = bytearray()
                async for part in resp.aiter_bytes():
                    buf.extend(part)
                    if len(buf) > MAX_BYTES:
                        raise SkipProcessing("file is over 50 MB")
                return bytes(buf)
        except httpx.TransportError as exc:
            raise PlatformError(f"download failed: {type(exc).__name__}") from exc
        finally:
            if own:
                await c.aclose()

    return download
