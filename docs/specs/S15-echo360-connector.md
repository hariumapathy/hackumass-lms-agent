# S15 — Echo360 connector

| | |
|---|---|
| **Status** | Draft |
| **Stage** | 2 |
| **Role** | A |
| **Depends on** | S11 (launch path), S13 (session path) |
| **Folders** | `backend/app/connectors/echo360/` |

## Purpose
Get the list of lecture recordings and their **captions/transcripts** for the student's courses, so the agent can answer "what did the professor say about X" with a timestamped link.

## Inputs
- Either a Canvas token (launch path) or an Echo360 session (S13), depending on the spike result below.
- `SyncScope`: `full` or `course`.

## Outputs
- `NCourse` link for each Echo360 section, matched to a Canvas course.
- `NMaterial(kind="transcript")` per recording that has captions: `title`, `recorded_at`, `cues` (list of `{start_s, end_s, text}`), `source_url` = recording page, `duration_s`.
- Recordings without captions: `NMaterial(kind="transcript", text=None, cues=None)` → S12 marks `skipped` ("no captions"), still listed so the UI can show it exists.

## Stage 2 spike (first 1–2 hours; record results here)
| Question | Result |
|---|---|
| Can a student token call Canvas `GET /api/v1/courses/:id/external_tools` and `.../external_tools/sessionless_launch?id=:tool_id` for the Echo360 tool, and does the returned URL log into Echo360 without Duo? | _TBD_ |
| Which Echo360 pages/JSON responses list a section's recordings (use browser devtools on our own course)? | _TBD_ |
| Where do captions come from (a captions/VTT download, or a transcript JSON)? | _TBD_ |
| Timestamp deep-link format for a recording page | _TBD_ |

**Decision rule:** if the launch path works, use it (no extra login). Otherwise use the S13 session path with `LoginSpec` for Echo360.

## Interface
```python
class Echo360Connector(Connector):
    platform = "echo360"
    def fetch(self, ctx, scope) -> AsyncIterator[NormalizedRecord]

def parse_recordings(payload: str | dict) -> list[RecordingInfo]   # pure; fixture-tested
def parse_captions(vtt_or_json: str) -> list[TranscriptCue]       # pure; fixture-tested
def deep_link(recording_url: str, start_s: int) -> str            # used by S23
```

## Behavior and rules
1. Only recordings from the current term; newest first; cap 60 recordings per course.
2. Captions parsed into cues with integer seconds; overlapping/duplicate cues de-duplicated.
3. `source_updated_at` = recording's updated timestamp if available, else `recorded_at`; captions added later must trigger reprocessing (compare a hash of the cue text).
4. Daily schedule (S10) + `fetch_latest` for "the latest lecture".
5. `deep_link` falls back to the plain recording URL if timestamp links aren't supported (citation then shows the timestamp as text).

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| No captions | Listed, `skipped`, UI shows "no transcript available" |
| Course has no Echo360 | No records; not an error |
| Launch URL expired mid-sync | Re-launch once; then `PlatformError` |
| Session redirect to login | `AuthExpired` |

## Acceptance criteria
- [ ] Spike results recorded in this spec
- [ ] For one real course, recordings with captions produce transcript chunks with correct timestamps (spot-check 3 against the video)
- [ ] `deep_link` verified manually to open at the right moment (or fallback documented)

## Test plan
| ID | Test | Type |
|---|---|---|
| S15-T01 | `parse_recordings` extracts IDs, titles, dates, URLs from fixture | connector |
| S15-T02 | `parse_captions` handles VTT (or JSON) with hours/minutes/seconds | unit |
| S15-T03 | Duplicate/overlapping cues de-duplicated | unit |
| S15-T04 | Recording without captions → material with no cues | connector |
| S15-T05 | Captions appearing later change the hash → reprocess | integration |
| S15-T06 | `deep_link` builds the timestamp URL (or falls back) | unit |

## Out of scope
Downloading video/audio, speech-to-text (stretch), slides embedded in Echo360.
