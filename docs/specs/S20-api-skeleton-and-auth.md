# S20 — Backend API skeleton and auth

| | |
|---|---|
| **Status** | Draft |
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
- [ ] Requests with a real Supabase session from the web app authenticate
- [ ] All routes (except the two public) reject missing/invalid tokens
- [ ] `/me` returns profile + connections; `DELETE /me/data` leaves nothing behind for that user

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
