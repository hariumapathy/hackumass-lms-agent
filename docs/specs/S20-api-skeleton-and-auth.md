# S20 — Backend API skeleton and auth

| | |
|---|---|
| **Status** | In progress (Hari): all done in DB mode except Storage cleanup (S12) and job cancellation (S10) in DELETE /me/data |
| **Stage** | 1 |
| **Role** | B |
| **Depends on** | S01, S02 |
| **Folders** | `backend/app/api/`, `backend/app/core/`, `backend/app/db/` |

## Purpose
The FastAPI application every endpoint lives in: settings, DB pool, authentication with Supabase JWTs, user scoping, error envelope, CORS, logging, rate limiting, and the account endpoints (`/me`, `/me/data`).

## Inputs
- HTTP requests with `Authorization: Bearer <Supabase access token>`.
- Env vars from S00.

## Outputs
- `current_user` dependency → `UserCtx(user_id, email)`; profile auto-created on first request.
- Consistent JSON errors (S02 envelope).
- `GET /health`, `GET /me`, `PATCH /me`, `DELETE /me/data`.

## Interface
```python
# core/settings.py: pydantic-settings, reads env (S00)
class Settings(BaseSettings): ...

# api/deps.py
async def current_user(authorization: str = Header(...)) -> UserCtx    # 401 on failure
async def db() -> AsyncIterator[AsyncConnection]                     # psycopg async pool

# db/repositories/*.py: every function takes user_id first
async def get_profile(conn, user_id: UUID) -> Profile | None
async def ensure_profile(conn, user_id: UUID, email: str) -> Profile

# core/clock.py
class Clock(Protocol): def now(self) -> datetime   # SystemClock, FixedClock (tests)
```

## Behavior and rules
1. **JWT verification:** verify signature against Supabase JWKS (`SUPABASE_JWKS_URL`) if set, else HS256 with `SUPABASE_JWT_SECRET`; check `exp`, `aud="authenticated"`; `sub` → `user_id`. Cache JWKS for 10 min.
2. **Every route except `/health` and `/calendar/{token}.ics` requires `current_user`.** A test asserts this over the route table.
3. **User scoping:** repositories require `user_id`; there is no repository function that reads user data without it. Lint-style test scans repository signatures.
4. DB access: `psycopg` 3 async pool; SQL in repository modules; results parsed into Pydantic models.
5. Errors: custom `AppError(code, message, status, retryable)`; global handlers map validation errors to `422 validation_error`, unknown exceptions to `500 internal` (no stack traces in responses; full trace in logs).
6. CORS: allow only `WEB_ORIGIN`.
7. Rate limit: `POST /chat` 10/min per user (in-memory token bucket; MVP single instance).
8. Logging: structured JSON logs with `request_id`, `user_id`, route, latency. **Never log tokens, cookies, message text or course content** at info level.
9. `DELETE /me/data`: deletes all rows for the user (cascade), Storage objects under `users/{user_id}/`, connection secrets; cancels queued jobs; returns 204. Does not delete the auth account (student can sign in again to an empty account).
10. `PATCH /me` validates `timezone` against IANA names and `model_choice` against `/models` (S26).

## Errors and edge cases
| Case | Expected behavior |
|---|---|
| Expired JWT | 401 `unauthorized` |
| Valid JWT, first request | Profile created with defaults, then request proceeds |
| DB unavailable | 503-style `internal` with `retryable: true` |

## Acceptance criteria
- [ ] Requests with a real Supabase session from the web app authenticate (unit-tested with a JWKS ES256 token; needs a live check once S30 signs in against the hosted project)
- [x] All routes (except the two public) reject missing/invalid tokens
- [ ] `/me` returns profile + connections; `DELETE /me/data` leaves nothing behind for that user (repository code written; waits for S01)

## Test plan
| ID | Test | Type |
|---|---|---|
| S20-T01 | Valid HS256 token → `UserCtx`; wrong secret → 401 | unit |
| S20-T02 | Expired token / wrong audience → 401 | unit |
| S20-T03 | Every route except public ones depends on `current_user` (route table scan) | unit |
| S20-T04 | Every repository function's first data param is `user_id` (signature scan) | unit |
| S20-T05 | First request creates a profile with defaults | integration |
| S20-T06 | Error envelope for 401, 404, 422, 500 | integration |
| S20-T07 | `DELETE /me/data` removes all rows + storage objects for the user only | integration |
| S20-T08 | `PATCH /me` rejects bad timezone and unknown model | integration |
| S20-T09 | Chat rate limit returns 429 after 10 requests/min | unit |
| S20-T10 | Logs never contain the Authorization header or message text | unit |

## Out of scope
Multi-instance rate limiting, admin roles, account deletion of the auth user.

## Implementation notes (2026-11-14, Hari)
- **Verification** (`app/core/auth.py`, library **PyJWT[crypto]**): the key is chosen by the token's `alg` header. ES256/RS256/EdDSA → JWKS (`SUPABASE_JWKS_URL`, cached 10 min, early refetch for an unknown `kid` at most every 30 s, last good keys kept if the endpoint is down; no keys at all → `503 internal, retryable`). HS256 → `SUPABASE_JWT_SECRET`. If both are set, both kinds are accepted (legacy tokens keep working during a key rotation). Our hosted project signs with **ES256** (checked against its JWKS). Requires `exp`, `sub` (a UUID), `aud="authenticated"`.
- `current_user(authorization)` keeps the S02 signature but no longer accepts any bearer string. The web app's demo/MSW mode is unaffected (it never calls the backend).
- **Rate limit:** `TokenBucket` (`app/core/ratelimit.py`), 10/min per user on `POST /chat` → 429 `rate_limited`, `retryable: true`. `create_app(clock=...)` injects the clock.
- **Logs:** `RequestLogMiddleware` (`app/core/logging.py`) writes one JSON line per request (`request_id`, `user_id`, method, route template, status, latency) to logger `app.request` and sets an `x-request-id` response header. Headers, query strings and bodies are never logged.
- **DB:** `app/db/pool.py` (psycopg 3 async pool, opened lazily, `dict_row`, outage → 503 retryable). `app/db/repositories/profiles.py`: `get_profile`, `ensure_profile`, `update_profile`, `delete_user_data`, all `(conn, user_id, ...)` (enforced by S20-T04). **Not wired into routes yet:** `/me`, `PATCH /me` and `DELETE /me/data` still return S02 mock data (with the real `user_id`) until S01's `profiles` table exists, so the frontend never sees 503s. Wiring them up and auto-creating the profile on first request is the first thing to do after S01 merges.
- **PATCH /me validation** is live now (IANA timezone, `model_choice` must be in `/models`) → 422 `validation_error`.
- **Tests:** `tests/unit/test_s20_auth.py` covers T01–T04, T06, T08–T10 and DB-down. `tests/integration/test_s20_db.py` (T05, T07) **skip with "pending S01"** until a local DB with the schema is running. The Storage half of T07 is skipped pending S12's storage helper, and job cancellation is pending S10. T06 runs as a unit test (no DB needed). Tests force `DATABASE_URL` to the local DB (or `TEST_DATABASE_URL`), so they can never touch the hosted project.
- **Update (2026-11-14, after S01):** with `DATA_SOURCE=db`, `/me` creates the profile on first call, `PATCH /me` persists, and `DELETE /me/data` deletes all of the student's rows (`tests/integration/test_s20_me_db.py`, `test_s20_db.py`). The agent uses the profile's timezone + model. Mock mode keeps the S02 demo student.
- **Windows gotcha:** psycopg async can't run on Windows' default Proactor event loop. `make api` uses `--reload`, which makes uvicorn pick a selector loop, so it works. Tests get a selector loop from the `pytest_asyncio_loop_factories` hook in `tests/conftest.py`. Running uvicorn on Windows **without** `--reload` would break DB calls.
