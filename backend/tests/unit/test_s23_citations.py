"""S23: citation validation and resolution (DB-backed T02, T05, T06, T09 wait for S01)."""

from datetime import UTC, datetime

import pytest

from app.agent.citations import (
    build_deep_link,
    resolve_rows,
    validate_citations,
    validate_ids,
)
from app.agent.tools.mock_source import MockToolData

CHUNKS = {
    8812: "[COMPSCI 311 · Lecture 7 slides · p.12]\nMemoization stores solutions to subproblems "
    "so each is solved once. A memoized recursive algorithm checks a table first.",
    9930: "so when we memoize, we're trading memory for time: we keep every answer.",
}


# --- S23-T01 ----------------------------------------------------------------------------------


def test_s23_t01_spec_example() -> None:
    r = validate_citations(
        "Memoization trades memory for time [cite:chunk_8812][cite:chunk_77].",
        {8812, 9930},
        CHUNKS,
    )
    assert r.clean_text == "Memoization trades memory for time [cite:chunk_8812]."
    assert r.valid_ids == [8812] and r.dropped_ids == [77]


def test_s23_t01_order_and_dedup() -> None:
    text = "A [cite:chunk_9930]. B [cite:chunk_8812]. C [cite:chunk_9930] [cite:chunk_5]."
    r = validate_citations(text, {8812, 9930}, CHUNKS)
    assert r.valid_ids == [9930, 8812] and r.dropped_ids == [5]
    assert r.clean_text == "A [cite:chunk_9930]. B [cite:chunk_8812]. C [cite:chunk_9930]."


# --- S23-T03: quote check ----------------------------------------------------------------------


def test_s23_t03_matching_quote_kept_fabricated_dropped() -> None:
    real = (
        'The slides say "memoization stores solutions to subproblems so each is solved once" '
        "[cite:chunk_8812]."
    )
    fake = (
        'The slides say "memoization is only useful for graph algorithms in practice" '
        "[cite:chunk_8812]."
    )
    assert validate_citations(real, {8812}, CHUNKS).valid_ids == [8812]
    r = validate_citations(fake, {8812}, CHUNKS)
    assert r.valid_ids == [] and r.dropped_ids == [8812]
    short = 'It is "memo time" [cite:chunk_8812].'  # under 6 words: not checked
    assert validate_citations(short, {8812}, CHUNKS).valid_ids == [8812]


# --- S23-T04: malformed markers ----------------------------------------------------------------


@pytest.mark.parametrize("marker", ["[cite:abc]", "[CITE:chunk_x]", "[cite:]", "[cite: x 1]"])
def test_s23_t04_malformed_markers_removed(marker: str) -> None:
    r = validate_citations(f"Fact {marker} here [cite:chunk_8812].", {8812}, CHUNKS)
    assert r.clean_text == "Fact here [cite:chunk_8812]."
    assert r.valid_ids == [8812]


@pytest.mark.parametrize("marker", ["[cite: chunk_8812]", "[cite:8812]", "[Cite: Chunk 8812]"])
def test_s23_t04_harmless_variants_normalized(marker: str) -> None:
    """Gemini writes '[cite: chunk_8812]' (with a space); keep those citations."""
    r = validate_citations(f"Fact {marker}.", {8812}, CHUNKS)
    assert r.clean_text == "Fact [cite:chunk_8812]." and r.valid_ids == [8812]
    unknown = validate_citations("Fact [cite: chunk_1].", {8812}, CHUNKS)
    assert unknown.clean_text == "Fact." and unknown.dropped_ids == [1]


def test_s23_t04_no_markers_untouched() -> None:
    text = "Plain answer with [brackets] and no citations."
    assert validate_citations(text, set(), {}).clean_text == text


# --- S23-T07: deep links -----------------------------------------------------------------------


def test_s23_t07_echo360_deep_link_timestamp_or_fallback() -> None:
    url = "https://example.echo360.com/lesson/nov11"
    assert build_deep_link("echo360", url, None, 1421) == f"{url}?time=1421"
    assert build_deep_link("echo360", url + "?a=1", None, 5) == f"{url}?a=1&time=5"
    assert build_deep_link("echo360", url, None, None) == url
    canvas = "https://example.instructure.com/courses/cs311/files/7"
    assert build_deep_link("canvas", canvas, 12, None) == canvas


# --- S23-T08 -------------------------------------------------------------------------------------


def test_s23_t08_validate_ids_for_study_sets() -> None:
    assert validate_ids([8812, 1, 8812, 9930, 2, 1], {8812, 9930}) == ([8812, 9930], [1, 2])


# --- resolution (mock data until S01; S23-T05 integration later) --------------------------------


async def test_s23_resolve_rows_fields_from_stored_data() -> None:
    data = MockToolData(now=datetime(2026, 11, 14, 17, tzinfo=UTC))
    rows = await data.chunks_by_id([9930, 8812, 7002])
    cites = resolve_rows(rows, [8812, 9930, 7002, 999])
    assert [c.chunk_id for c in cites] == [8812, 9930, 7002]  # unknown 999 skipped
    slide, transcript, post = cites
    assert slide.page == 12 and slide.platform == "canvas" and slide.url == slide.deep_link
    assert transcript.deep_link.endswith("?time=1421") and transcript.start_s == 1421
    assert post.platform == "piazza" and post.url.startswith("https://example.piazza.com/")
    assert all(c.status == "current" and c.quote and not c.quote.startswith("[") for c in cites)
