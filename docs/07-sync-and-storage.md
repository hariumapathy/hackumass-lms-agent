# 07 — Sync and Storage

**Sync** = a background worker regularly copies each student's course data into our database. The agent answers from *our copy*, not by calling Canvas/Gradescope live.

## Why not pull live on every question?
Live pulling is slow (10–30+ s per question once the AI chains calls; cloud-browser pages take 2–5 s each) and expensive (raw API data in the model's context). More importantly, core features **need a stored copy**:

- **Search** across hundreds of slides and transcripts (must be read and indexed ahead of time)
- **Change detection** ("midterm moved"), which needs the old version to compare
- **Merging duplicates** across Canvas, Piazza, syllabus, email
- **Instant dashboard**, plus graceful behavior when a session expired ("Gradescope last synced 2 days ago")
- Staying under Canvas rate limits; demo reliability

**Hybrid:** background sync for freshness, plus a **targeted live refresh** of one course before high-stakes asks ("prep me for the midterm"), plus an optional link check on click ([04](04-citations-and-freshness.md)).

## Pipeline (per student, per source)
1. **Schedule**: job queue says "sync Canvas for Hari" is due.
2. **Fetch**: incremental where possible (Canvas `updated_at`; Gradescope/Echo360 via saved session).
3. **Normalize** into common types: **Item** (assignment/exam/quiz), **Material** (file/slides/transcript), **Post** (announcement/Piazza/email), **Course**.
4. **Diff** by `(platform, platform_id)` + `content_hash` (a fingerprint of the content):
   new → insert · changed → new version + log in `changes` · unchanged → bump `last_synced_at` (most records, so syncs are cheap) · missing → mark `removed`, never delete.
5. **Merge** the same item across sources (course + nearby date + similar title).
6. **Process new/changed files only**: download → extract text per page/slide/timestamp → split into chunks → embed → store.
7. **Notify**: refresh dashboard; flag important changes.

| Data | Frequency |
|---|---|
| Assignments, announcements, Piazza | 15–30 min |
| Grades | hourly |
| Files | checked every sync; processed only when `updated_at` changes |
| Echo360 recordings | ~daily |
| On demand | "Sync now" button; before exam prep |

## Storage (all in Supabase)
```
Postgres     courses, items, materials, posts, changes, chunks (+ embeddings via pgvector)
Storage      users/{user_id}/canvas/{course_id}/files/{file_id}/v{n}.pdf
             users/{user_id}/echo360/{course_id}/{recording_id}/transcript.vtt
Secrets      Canvas tokens, session cookies (encrypted, separate, worker-only, never sent to the AI)
```

**Every source-backed row** has: `user_id`, `platform`, `platform_id`, `source_url` (built from platform IDs; this is where citation links come from), `content_hash`, `source_updated_at`, `last_synced_at`, `status` (active | changed | removed).

**Chunks** (what search runs over): `id`, `material_id`, `page` or `timestamp`, `text`, `embedding`. A question is embedded, Postgres returns the closest chunks *filtered by student and course*, and those chunk IDs are what the AI cites.

**Isolation:** Postgres Row Level Security makes the database refuse to return another student's rows, even if our code has a bug.

**Size:** roughly a few hundred MB of originals per student; likely fine on Supabase's free tier for a few demo accounts (check limits). If tight, keep only extracted text + the Canvas link. Later: store shared course files once per course (needs permission care).

## Where it runs
Sync can't live in Vercel functions (time limits; Playwright needs a real server). Use **one Node.js worker** on a small host (Railway / Render / Fly.io) with a **Postgres job queue** (e.g. pg-boss) for scheduling, retries and one-sync-per-student-at-a-time. Alternative: a hosted job service (Inngest / Trigger.dev).
