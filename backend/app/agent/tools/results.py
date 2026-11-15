"""ToolResult envelope, chunk-ID collection, untrusted wrapping and size limits (S21)."""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.coverage import Coverage

# ~6,000 tokens at ~4 characters per token (S21 rule 9). A rough count is enough here.
MAX_RESULT_CHARS = 24_000
MIN_TEXT_CHARS = 300

POST_SOURCES = {"announcement": "canvas", "piazza": "piazza", "email": "email"}


class ToolResult(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    truncated: bool = False
    note: str | None = None


def collect_chunk_ids(result: ToolResult) -> set[int]:
    found: set[int] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                if key == "chunk_id" and isinstance(inner, int):
                    found.add(inner)
                else:
                    walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(result.results)
    return found


def collect_chunk_texts(result: ToolResult) -> dict[int, str]:
    """chunk_id -> text for every result row (or nested row) that carries both."""
    found: dict[int, str] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            cid, text = value.get("chunk_id"), value.get("text")
            if isinstance(cid, int) and isinstance(text, str):
                found[cid] = text
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(result.results)
    return found


def wrap_untrusted(text: str, source: str) -> str:
    """Mark synced third-party text as data. The text can't close the wrapper early."""
    safe = text.replace("</untrusted", "&lt;/untrusted").replace("<untrusted", "&lt;untrusted")
    return f'<untrusted source="{source}">{safe}</untrusted>'


def wrap_post_text(post_kind: str, text: str) -> str:
    """Posts (announcements, Piazza, email) are untrusted; slides/transcripts stay plain."""
    return wrap_untrusted(text, POST_SOURCES.get(post_kind, post_kind))


def _size(result: ToolResult) -> int:
    return len(result.model_dump_json())


def truncate_result(result: ToolResult, limit: int = MAX_RESULT_CHARS) -> ToolResult:
    """Shorten long `text` fields, then drop trailing (lowest-ranked) results until it fits."""
    if _size(result) <= limit:
        return result
    out = result.model_copy(deep=True)
    out.truncated = True
    cap = max(MIN_TEXT_CHARS, limit // max(1, len(out.results)))
    for row in out.results:
        text = row.get("text")
        if isinstance(text, str) and len(text) > cap:
            row["text"] = text[:cap] + "…"
    while out.results and _size(out) > limit:
        out.results.pop()
    return out
