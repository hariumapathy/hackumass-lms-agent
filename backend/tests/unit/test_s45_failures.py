"""S45 classification is deterministic and emits only safe categories/codes."""

import httpx
import pytest


def status_error(code):
    request = httpx.Request("POST", "https://example.invalid/embeddings?secret=synthetic-secret")
    return httpx.HTTPStatusError(
        "synthetic private provider response",
        request=request,
        response=httpx.Response(code, request=request),
    )


@pytest.mark.parametrize(
    "code,kind",
    [
        (429, "retry"),
        (500, "retry"),
        (503, "retry"),
        (401, "configuration"),
        (403, "configuration"),
        (400, "configuration"),
        (404, "configuration"),
    ],
)
def test_s45_t01_http_failure_classification_is_content_free(code, kind):
    from app.sync.processing.failures import classify

    failure = classify(status_error(code))
    assert failure.kind == kind
    assert "synthetic" not in str(failure) and "example.invalid" not in str(failure)


def test_s45_t01_storage_timeout_and_extract_classification():
    from app.sync.processing.extract import ExtractError
    from app.sync.processing.failures import classify
    from app.sync.processing.storage import StorageError

    assert classify(httpx.ReadTimeout("synthetic secret")).kind == "retry"
    assert classify(StorageError("synthetic secret", status_code=503)).kind == "retry"
    assert classify(StorageError("synthetic secret", status_code=403)).kind == "configuration"
    assert classify(ExtractError("synthetic document text")).kind == "permanent"


@pytest.mark.parametrize("status", [408, 409, 425])
async def test_s45_t01_download_transient_status_is_not_permanent(status):
    import respx

    from app.connectors.base import DownloadRef, PlatformError
    from app.sync.processing.storage import http_downloader

    with respx.mock() as router:
        router.get("https://canvas.example/transient").respond(status)
        with pytest.raises(PlatformError):
            await http_downloader(None)(DownloadRef(url="https://canvas.example/transient"))
