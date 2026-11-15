# S23 — Citations

| | |
|---|---|
| **Status** | In progress (Hari): validation + DB resolution done; `GET /citations` route still on mock data |
| **Stage** | 1 (validation + resolution); deep links completed in Stage 2 with S15 |
| **Role** | B |
| **Depends on** | S21, S22 |
| **Folders** | `backend/app/agent/citations.py`, `backend/app/api/routes/citations.py` |

## Purpose
Guarantee that every reference the student sees is real: the model cites by chunk ID, our code validates and resolves those IDs into links built from stored data. Hallucinated links are impossible; wrong-but-real citations are caught by the quote check. Background: [04](../04-citations-and-freshness.md).

## Inputs
- Final answer text with markers `[cite:chunk_<id>]`.
- `allowed_chunk_ids` collected by tools during the run (S21).
- Study set payloads containing `chunk_ids` (S24).

## Outputs
- `clean_text`: invalid markers removed; valid markers kept (frontend renders them as chips).
- `citations: list[Citation]` (S02 type), in first-appearance order, de-duplicated.
- `dropped: list[int]`: invalid IDs (logged in `agent_runs`).

## Interface
```python
MARKER = re.compile(r"\[cite:chunk_(\d+)\]")

def validate_citations(text: str, allowed: set[int], chunk_texts: dict[int, str]) -> ValidationResult
    # -> clean_text, valid_ids (ordered, unique), dropped_ids

def validate_ids(ids: list[int], allowed: set[int]) -> tuple[list[int], list[int]]   # for study sets

async def resolve(conn, user_id: UUID, ids: list[int]) -> list[Citation]
def build_deep_link(platform: Platform, source_url: str, page: int | None, start_s: int | None) -> str
```

## Behavior and rules
1. **Validation:** a marker is valid only if its ID ∈ `allowed` **and** the chunk belongs to the user. Invalid markers are removed from the text (along with one adjacent space).
2. **Quote check:** if the sentence containing a valid marker includes a quoted span (`"..."`, ≥ 6 words), that span must fuzzy-match the cited chunk's text (`rapidfuzz.partial_ratio ≥ 85`); otherwise the marker is dropped (counted in `dropped`).
3. **Resolution** joins `chunks` → `materials`/`posts` → `courses`; returns `title`, `kind`, `platform`, `course_code`, `page`/`start_s`/`end_s`, `url` (= stored `source_url`), `deep_link`, `quote` (first ~200 chars of chunk text without the context header), `last_synced_at`, `status`.
4. **Status:** `current` (chunk `is_current` and source `active`); `changed` (chunk not current or source `changed` after the message time); `removed` (source `removed`); `locked` (set by the optional click-time check if the platform returns forbidden).
5. **Deep links:** Canvas file → `source_url` (page shown in the citation card; Canvas viewer page anchors are unreliable); Echo360 → `deep_link()` from S15; posts → `source_url`.
6. `GET /citations?ids=` resolves IDs for the current user only (used when re-opening old conversations to refresh status).
7. The frontend never builds URLs; it only renders `url`/`deep_link` from this output.

## Example
Text: `Memoization trades memory for time [cite:chunk_8812][cite:chunk_77].` with allowed `{8812, 9930}` →
clean_text: `Memoization trades memory for time [cite:chunk_8812].`, citations: `[{chunk_id: 8812, title: "Lecture 7 slides", page: 12, url: "...", status: "current", ...}]`, dropped: `[77]`.

## Acceptance criteria
- [ ] No citation reaches the UI unless it came from a tool result in that run
- [ ] Every citation has a URL from the DB
- [ ] Changed/removed sources show the right status

## Test plan
| ID | Test | Type |
|---|---|---|
| S23-T01 | Valid IDs kept, unknown IDs removed, order + de-dup preserved | unit |
| S23-T02 | ID of another user's chunk is dropped even if "allowed" is tampered | integration |
| S23-T03 | Quote check: matching quote kept, fabricated quote dropped | unit |
| S23-T04 | Malformed markers (`[cite:abc]`, `[cite: chunk_1]`) left as text or removed consistently | unit |
| S23-T05 | Resolution returns all Citation fields for material and post chunks | integration |
| S23-T06 | Status: non-current chunk → changed; removed source → removed | integration |
| S23-T07 | Echo360 deep link includes timestamp (or falls back) | unit |
| S23-T08 | `validate_ids` for study sets splits valid/dropped | unit |
| S23-T09 | `GET /citations` only resolves the caller's chunks | integration |

## Out of scope
Click-time live link checking (optional, stretch), rendering (S33).

## Implementation notes (2026-11-14, Hari)
- `backend/app/agent/citations.py`: `validate_citations`, `validate_ids`, `build_deep_link`, `to_citation`, `resolve_rows`. Tests: `tests/unit/test_s23_citations.py` (T01, T03, T04, T07, T08 + resolution on mock rows).
- **Chunk texts for the quote check** come from the run itself: `invoke` (S21) stores each returned chunk's text in `RunCtx.chunk_texts`, so no extra DB read. The `[COURSE · Title · p.N]` header is stripped before matching. Library: **rapidfuzz** (`partial_ratio ≥ 85`, quotes of 6+ words, straight or curly quotes).
- **Malformed markers** (`[cite:abc]`, `[cite: chunk_1]`, `[CITE:…]`) are **removed**, along with one space before them, so students never see raw markers.
- **Echo360 deep link:** `source_url` + `?time=<start_s>` (matches the S02 mock). The S15 spike confirms the real format; until then, no timestamp falls back to `source_url`.
- **Resolution** goes through `ToolData.chunks_by_id` (one student's data), so another student's chunk ID never resolves. Today that's `MockToolData`; the DB version (join chunks → materials/posts → courses, status rules 4) arrives with S01. **Still to do after S01:** T02, T05, T06, T09 (integration) and wiring `GET /citations` to real data.
