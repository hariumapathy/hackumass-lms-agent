"""S12 file processing: extract -> chunk -> embed -> store (docs/specs/S12-file-processing.md)."""

from app.sync.processing.chunker import ChunkDraft, chunk, count_tokens, header
from app.sync.processing.extract import (
    MAX_BYTES,
    MAX_PAGES,
    Extracted,
    ExtractError,
    SkipProcessing,
    Unit,
    extract,
    extract_transcript,
)
from app.sync.processing.process import MaterialSource, process_material, process_post
from app.sync.processing.storage import (
    BUCKET,
    Downloader,
    Storage,
    StorageError,
    SupabaseStorage,
    delete_user_files,
    get_storage,
    http_downloader,
    storage_path,
)

__all__ = [
    "BUCKET",
    "MAX_BYTES",
    "MAX_PAGES",
    "ChunkDraft",
    "Downloader",
    "ExtractError",
    "Extracted",
    "MaterialSource",
    "SkipProcessing",
    "Storage",
    "StorageError",
    "SupabaseStorage",
    "Unit",
    "chunk",
    "count_tokens",
    "delete_user_files",
    "extract",
    "extract_transcript",
    "get_storage",
    "header",
    "http_downloader",
    "process_material",
    "process_post",
    "storage_path",
]
