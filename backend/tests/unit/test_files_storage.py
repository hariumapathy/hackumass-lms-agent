"""Storage download for the in-app file viewer (split-2026-11-15 B2): private bucket."""

import httpx
import respx

from app.sync.processing.storage import SupabaseStorage

URL = "http://127.0.0.1:54321"


async def test_files_storage_download_returns_bytes_or_none() -> None:
    with respx.mock() as router:
        ok = router.get(f"{URL}/storage/v1/object/materials/users/u/a.pdf").respond(
            content=b"%PDF", headers={"content-type": "application/pdf"}
        )
        router.get(f"{URL}/storage/v1/object/materials/users/u/gone.pdf").respond(
            400, json={"statusCode": "404", "error": "not_found", "message": "Object not found"}
        )
        async with httpx.AsyncClient() as client:
            storage = SupabaseStorage(URL, "sb_secret_x", client=client)
            assert await storage.download("users/u/a.pdf") == b"%PDF"
            assert await storage.download("users/u/gone.pdf") is None
        assert ok.calls[0].request.headers["apikey"] == "sb_secret_x"
