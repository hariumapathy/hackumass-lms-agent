# 04 — Citations and Freshness

**Goal:** every link a student sees is real, points to the right place, and is up to date, even though we sync periodically.

**Core rule: the LLM never writes URLs.** Every link is built from synced data, so a made-up link is structurally impossible. The remaining problem is staleness.

## 1. Links come from platform IDs, not generation
Each synced record stores a canonical URL built from the platform's stable IDs:

| Source | Stored canonical link |
|---|---|
| Canvas assignment | `umass.instructure.com/courses/{course_id}/assignments/{id}` |
| Canvas file / slides | `/courses/{course_id}/files/{file_id}` (+ page number we parsed) |
| Canvas announcement | `/courses/{course_id}/discussion_topics/{id}` |
| Piazza | `piazza.com/class/{class_id}/post/{post_number}` |
| Gradescope | `gradescope.com/courses/{id}/assignments/{id}` |
| Echo360 | recording page URL + timestamp |

Store the **page** URL, never the direct download link — Canvas download URLs carry tokens that expire within hours.

## 2. The model cites by ID; our code renders the link
1. Retrieval tools return chunks tagged with IDs (`chunk_8812`) and metadata (course, file, page/timestamp, url).
2. System prompt: cite only as `[cite:chunk_8812]`; never write URLs.
3. The renderer looks up each ID in the DB and draws the citation chip from the stored record.
4. **Validation:**
   - A cited ID that wasn't in this turn's tool results is dropped and logged.
   - Any raw URL in model text is rendered as plain text, not a link.
   - If the model quotes a passage, check the quote actually appears in the cited chunk; drop the citation if not.

Worst case becomes "cited the wrong slide," not "invented a link" — and the quote check catches most of that.

## 3. Keeping links fresh between syncs

**Every sync** (pipeline and cadence in [07](07-sync-and-storage.md))
- **Changed** source → new version kept alongside the old; citations to it show "changed since you last saw it."
- **Removed** source → row marked `removed`, not deleted; citations show "removed from Canvas on Nov 12" instead of a dead link.

**Before high-stakes questions**
- "Prep me for the midterm" triggers a quick targeted re-sync of that course first; UI shows "Synced just now."

**On click**
- Citation card shows the exact quoted text, page/timestamp, and "last synced." Opens the source in the student's own logged-in browser.
- Optional live check at click time using the student's token/session. If gone or forbidden → show our saved copy with "This item was moved or removed on Canvas."
- We always keep the cited text, so the student can see exactly what the answer was based on even if the source later changed.

## 4. Edge cases
- **Locked / unpublished items** may return forbidden even though we synced them earlier → show saved copy + "currently locked."
- **Same item, several sources** (exam in Canvas + Piazza + email) → one item, all three source links shown. Also demonstrates dedupe working.
- **Precise anchors:** Canvas's file viewer doesn't reliably jump to a page → render the cited page from our copy with an "Open in Canvas" button. Echo360 timestamps can deep-link to the moment.
- **Production:** replace polling with Canvas Live Events (real-time feed; needs a university-issued key).

## Demo moment: "Why trust this"
Click three citations live: one opens the exact slide, one jumps to the Echo360 timestamp, one shows "this announcement was edited after you saw it." Line: *"The AI can't make up a link — every reference comes from synced data and is checked before it's shown."*
