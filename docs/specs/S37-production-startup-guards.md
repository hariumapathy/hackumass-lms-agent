# S37 — Fail-closed production startup

**Status:** Implemented on review branch (not merged); Ready authorization (Neal; user explicitly authorized sequential implementation 2026-11-24). **Package:** P01a, startup subfeature only. **Owner:** shared backend/configuration. **No DB/API/SSE/seed contract change.** Gemini remains the application provider. Work stays on `codex/post-hackathon-implementation`, unmerged until user says done.

## Problem and behavior

A hosted server currently accepts defaults that show sample course data or scripted chat, use fake embeddings and start a local headed login browser. Production must refuse these combinations before serving requests or starting workers. Development and the separate seeded backup must still work unchanged. This spec does not claim to configure Google OAuth, hosting or credentials.

Add explicit `APP_ENV=development|test|production` (default development). In production require `DATA_SOURCE=db`, `CHAT_MODE=agent`, `EMBEDDINGS_PROVIDER=gemini`, nonempty Gemini/service-role credentials, a valid Fernet key, a non-local Postgres URL with explicit TLS (`sslmode=require|verify-ca|verify-full`), HTTPS public Supabase/API/web URLs, and the configured Supabase project's exact HTTPS JWKS URL. Public URLs reject embedded credentials/query/fragment and loopback/private/link-local IPs or local hostnames. Web origin and Supabase URL must be origins; public API may have a path prefix. No DNS/network validation during settings construction.

Introduce `BROWSER_PROVIDER=disabled` for a Canvas-only hosted deployment. Production rejects local and currently unimplemented hosted browser modes; disabled login endpoints report unavailable. Requesting hosted login in any environment must fail explicitly, never silently open a local window. Existing local development logins remain enabled. Explicitly disabling a connector capability is not disconnecting or deleting its existing imported data.

Errors identify invalid setting names/reasons without values. Settings validation and repr must not reveal database credentials or secret values. No real secrets are added to fixtures/docs. Existing JWT issuer hardening is the next separate fix, not part of S37.

## Test cases (write executable tests before implementation)

| ID | Case / expected result |
|---|---|
| S37-T01 | Development defaults retain mock/scripted fallback/local browser behavior; existing tests remain green |
| S37-T02 | Valid synthetic production configuration is accepted without network/model calls |
| S37-T03 | Mock data, auto/scripted chat, fake/unsupported embeddings, local/hosted browser rejected in production |
| S37-T04 | Missing/blank model/Storage credential or invalid/missing encryption key rejected |
| S37-T05 | HTTP/local/private/credential-bearing/query/fragment public URLs and non-origin web/Supabase URLs rejected |
| S37-T06 | Nonmatching project JWKS, insecure/local/malformed database URL or missing TLS rejected |
| S37-T07 | Disabled and unbuilt hosted live-login requests fail clearly; no local browser constructed |
| S37-T08 | Validation/repr of bad settings does not expose synthetic secret/database values |
| S37-T09 | Canonicalize valid web origin for exact browser CORS matching |

## Design plan

Validate once at the shared Settings boundary using an after-validator, so API and worker configuration use the same rule. Keep environment mode explicit to avoid accidental changes in local demos. Use parsed URL components and IP classification, not substring checks or network requests. Aggregate setting names into one sanitized operator message. Add `hide_input_in_errors` and suppress sensitive database URI repr. Browser manager checks capability before allocating a provider; no mock API response/schema change.

## Implementation plan

1. Add failing unit tests for production configuration and login-provider construction; record the observed failure.
2. Extend Settings/env example; add pure validation helpers and validation guard. Add disabled provider and manager fail-closed branch.
3. Run focused tests, all offline backend tests, ruff/format/pyright; integration suite if local Docker is available. No live model/platform calls.
4. Document valid operator configuration, local behavior and known deployment limits. Update devlog/progress/spec index, commit and push this fix before starting S38.

## Acceptance / validation

- [x] Production cannot silently show demo/scripted/fake data
- [x] Disabled/unimplemented hosted login cannot fall back to a local browser
- [x] Existing development behavior and tests retained
- [x] Secret-safe configuration diagnostics verified

Evidence: 32 focused tests failed before implementation, then passed; security review added 11 failing IP/libpq/CORS regressions, then all 43 focused passed. Final full backend suite: 557 passed, 1 skipped, 1 expected failure against local Supabase after Docker CLI startup; frontend baseline: 92 passed. Ruff/format/pyright checked; current startup security review recorded in devlog. No live platforms/model calls. [Operator configuration](../deployment/production-configuration.md).

Security-review corrections: normalize HTTP URL/IP forms with Pydantic; reject libpq transport overrides/noncanonical numeric local destinations; canonicalize web origin for CORS. Review and red/green evidence preserved in devlog.
