"""S45 safe processing failure categories. Never preserve provider response/source text."""

import httpx

from app.connectors.base import AuthExpired, PlatformError, SourceAccessError
from app.core.crypto import CryptoError
from app.core.embeddings import EmbeddingsConfigError
from app.sync.processing.extract import ExtractError
from app.sync.processing.storage import StorageError


class ProcessingFailure(Exception):
    def __init__(self, kind: str, code: str):
        self.kind, self.code = kind, code
        super().__init__("Course content could not be prepared.")


class RetryableProcessingError(ProcessingFailure, PlatformError):
    def __init__(self, code: str):
        super().__init__("retry", code)


def classify(error: Exception) -> ProcessingFailure:
    if isinstance(error, ProcessingFailure):
        return error
    if isinstance(error, (SourceAccessError, AuthExpired)):
        return ProcessingFailure("source_auth", "source_access")
    if isinstance(error, (CryptoError, EmbeddingsConfigError)):
        return ProcessingFailure("configuration", "service_configuration")
    if isinstance(error, ExtractError):
        return ProcessingFailure("permanent", "extraction_failed")
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
    elif isinstance(error, StorageError):
        code = error.status_code
    else:
        code = None
    if code is not None:
        if code in {408, 409, 425, 429} or code >= 500:
            return RetryableProcessingError("service_unavailable")
        return ProcessingFailure("configuration", "service_configuration")
    if isinstance(error, (httpx.TransportError, TimeoutError, PlatformError, StorageError)):
        return RetryableProcessingError("service_unavailable")
    # Unknown errors get a finite repair budget, never an unlimited retry loop or raw error text.
    return RetryableProcessingError("processing_failed")
