"""Citations (S23): validate the model's `[cite:chunk_<id>]` markers and resolve them into links
built from stored data. The model never writes URLs; anything it cites must have come back from
a tool in this run (`allowed`), and a quoted span must actually appear in the cited chunk.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz

from app.agent.tools.data import ChunkRow
from app.api import schemas as s

MARKER = re.compile(r"\[cite:chunk_(\d+)\]")
# Harmless variants models write ("[cite: chunk_12]", "[cite:12]", "[Cite: Chunk 12]") are
# normalized to the canonical marker first; anything else citation-like is removed.
_LENIENT = re.compile(r"\[\s*cite\s*:\s*(?:chunk[_\s]?)?(\d+)\s*\]", re.IGNORECASE)
# Anything that looks like a citation attempt but isn't a valid marker: removed consistently.
_ANY_CITE = re.compile(r"\[\s*cite\s*:[^\]]*\]", re.IGNORECASE)
_QUOTE = re.compile(r"[\"“]([^\"”]+)[\"”]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
QUOTE_MIN_WORDS = 6
QUOTE_MIN_SCORE = 85
QUOTE_PREVIEW_CHARS = 200


@dataclass
class ValidationResult:
    clean_text: str
    valid_ids: list[int] = field(default_factory=list)
    dropped_ids: list[int] = field(default_factory=list)


def _strip_header(text: str) -> str:
    """Tool results prefix chunk text with '[COURSE · Title · p.N]\\n'; drop it for matching."""
    return text.split("\n", 1)[1] if text.startswith("[") and "\n" in text else text


def _quote_ok(sentence: str, chunk_text: str | None) -> bool:
    quotes = [q for q in _QUOTE.findall(sentence) if len(q.split()) >= QUOTE_MIN_WORDS]
    if not quotes:
        return True
    if not chunk_text:
        return False
    body = _strip_header(chunk_text).lower()
    return all(fuzz.partial_ratio(q.lower(), body) >= QUOTE_MIN_SCORE for q in quotes)


def _sentences_with_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return spans


def normalize_markers(text: str) -> str:
    return _LENIENT.sub(lambda m: f"[cite:chunk_{m.group(1)}]", text)


def validate_citations(
    text: str, allowed: set[int], chunk_texts: dict[int, str]
) -> ValidationResult:
    text = normalize_markers(text)
    spans = _sentences_with_spans(text)

    def sentence_at(pos: int) -> str:
        for a, b in spans:
            if a <= pos <= b:
                return text[a:b]
        return ""

    keep: list[tuple[int, int]] = []  # marker spans to keep
    valid: list[int] = []
    dropped: list[int] = []
    for m in MARKER.finditer(text):
        cid = int(m.group(1))
        ok = cid in allowed and _quote_ok(sentence_at(m.start()), chunk_texts.get(cid))
        if ok:
            keep.append(m.span())
            if cid not in valid:
                valid.append(cid)
        elif cid not in dropped:
            dropped.append(cid)

    kept = set(keep)

    def replace(m: re.Match[str]) -> str:
        return m.group(0) if m.span() in kept else ""

    # Remove every citation-looking token we don't keep, plus one space before it.
    pattern = re.compile(r" ?" + _ANY_CITE.pattern, re.IGNORECASE)
    out, last = [], 0
    for m in pattern.finditer(text):
        token_start = m.start() + (1 if text[m.start()] == " " else 0)
        if (token_start, m.end()) in kept:
            continue
        out.append(text[last : m.start()])
        last = m.end()
    out.append(text[last:])
    clean = "".join(out)
    return ValidationResult(clean_text=clean, valid_ids=valid, dropped_ids=dropped)


def validate_ids(ids: list[int], allowed: set[int]) -> tuple[list[int], list[int]]:
    """For study-set payloads (S24): (valid in order, de-duplicated; dropped)."""
    valid: list[int] = []
    dropped: list[int] = []
    for cid in ids:
        bucket = valid if cid in allowed else dropped
        if cid not in bucket:
            bucket.append(cid)
    return valid, dropped


def build_deep_link(platform: str, source_url: str, page: int | None, start_s: int | None) -> str:
    """Canvas files/pages and posts: the stored URL (page shown on the card; Canvas viewer anchors
    are unreliable). Echo360: jump to the timestamp (format confirmed by the S15 spike)."""
    if platform == "echo360" and start_s is not None:
        sep = "&" if "?" in source_url else "?"
        return f"{source_url}{sep}time={start_s}"
    return source_url


def to_citation(row: ChunkRow, message_time: datetime | None = None) -> s.Citation:
    status = row.status if row.status in {"current", "changed", "removed", "locked"} else "current"
    quote = _strip_header(row.text)
    if len(quote) > QUOTE_PREVIEW_CHARS:
        quote = quote[:QUOTE_PREVIEW_CHARS].rsplit(" ", 1)[0] + "…"
    return s.Citation(
        chunk_id=row.chunk_id,
        title=row.title,
        kind=row.kind,
        platform=row.platform,  # type: ignore[arg-type]
        course_code=row.course_code,
        page=row.page,
        start_s=row.start_s,
        end_s=row.end_s,
        url=row.source_url,
        deep_link=build_deep_link(row.platform, row.source_url, row.page, row.start_s),
        quote=quote,
        last_synced_at=row.last_synced_at,
        status=status,  # type: ignore[arg-type]
    )


def resolve_rows(rows: list[ChunkRow], ids: list[int]) -> list[s.Citation]:
    """Citations in `ids` order; IDs without a row (not this student's) are skipped."""
    by_id = {r.chunk_id: r for r in rows}
    return [to_citation(by_id[i]) for i in ids if i in by_id]
