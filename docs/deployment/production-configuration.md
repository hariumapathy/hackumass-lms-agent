# Production configuration gate (S37)

The API and worker now share an explicit environment gate. This is a prerequisite, not a completed deployment. Local demos default to `APP_ENV=development` and retain existing behavior; never use demo/seed/reset commands for production.

## Server requirements

| Setting | Production requirement |
|---|---|
| `APP_ENV` | `production` (operator must set explicitly) |
| `DATA_SOURCE`, `CHAT_MODE` | `db`, `agent` |
| `EMBEDDINGS_PROVIDER` | `gemini`; fake and currently unsupported alternatives refused |
| `GEMINI_API_KEY` | Nonempty server secret; current Gemini model is retained |
| `SUPABASE_SERVICE_ROLE_KEY` | Nonempty server secret; never a frontend public variable |
| `ENCRYPTION_KEY` | Valid Fernet key from managed secret storage; preserve for existing encrypted credentials |
| `DATABASE_URL` | Non-local Postgres connection, explicit `sslmode=require`, `verify-ca` or preferably `verify-full`; verify provider CA/hostname requirements |
| `SUPABASE_URL`, `WEB_ORIGIN` | Public HTTPS origins, no userinfo/query/fragment/path |
| `PUBLIC_API_URL` | Public HTTPS URL, optional deployment path prefix; no userinfo/query/fragment |
| `SUPABASE_JWKS_URL` | Exactly the selected Supabase URL plus `/auth/v1/.well-known/jwks.json` |
| `BROWSER_PROVIDER` | `disabled`; local is for laptop demos and hosted login is not built |

Canonical browser web origins are normalized for CORS. Noncanonical numeric local hosts and libpq query transport overrides are rejected. Validation uses parsed URL/IP rules, not DNS resolution or outbound calls. It does not prove that services are reachable or that keys are valid/authorized. Validate connectivity in isolated staging. Private managed Postgres addresses are allowed; public HTTP service URLs are not. No real keys/URLs should be copied into tracked examples or diagnostic output.

A safe configuration-only check from `backend/` is `uv run python -c 'from app.core.settings import get_settings; get_settings(); print("configuration valid")'`. Failure reports invalid setting names without values. Never print the Settings object or `.errors()` input payloads when debugging secrets. Production API/worker import/startup also loads this shared gate automatically.

## Connector availability

`BROWSER_PROVIDER=disabled` makes live-account login unavailable; it does not delete retained records. `hosted` no longer falls back to a local browser, even in development. Existing local browser logins work only in local mode. Hosted Gradescope/Piazza need their own future implementation and capability-aware UI; keep their hosted controls gated until then.

## Remaining release work

Frontend production/demo fallbacks, stricter JWT issuer validation, shared quotas, full deletion, hosted login, readiness/operational checks and deployment artifacts are still separate pending fixes. Do not call the product production-ready based on this configuration gate alone. No new model provider credentials or hosted service were provisioned by S37.
