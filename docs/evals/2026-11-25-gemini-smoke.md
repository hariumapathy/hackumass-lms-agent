# Gemini live-provider smoke — 2026-11-25

Manual, separately authorized provider check; ordinary automated tests still never call a real model/platform. Only synthetic/public demo-semester data was sent. No API key, token, private student content or provider response headers are recorded.

The previously supplied Gemini credential passed model metadata lookup (HTTP200) and was saved only in the ignored root `.env`. A512-token synthetic chat returned an answer with finish reason `stop`. A16-token probe had no answer, so it was not treated as successful chat verification.

The existing app evaluation harness then ran only G01 against the mock semester on configured Gemini3.5 Flash: **1/1 passed**,9.72seconds, one `get_items` tool call, zero errors/dropped citations. Usage:5,463 input/216 output tokens across two model calls. This checks the actual agent/tool/streaming path; it does not measure real-course retrieval quality or the proposed120-question benchmark. No provider/cost system was changed.

Local HTTP smoke: web homepage/settings200, API `/health`200 and unauthenticated `/me`401. Web: http://localhost:3000; API: http://127.0.0.1:8000. Worker is paused while DB fixture tests run and restarted only at verified checkpoints. No authenticated real Canvas/Google flow was freshly exercised in this smoke.
