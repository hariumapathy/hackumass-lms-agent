# S38 — Bind authentication tokens to a trusted issuer

**Status:** Implemented on review branch, not merged (user-authorized sequential implementation, 2026-11-24). **Package:** P01a authentication subfeature, after completed S37. **No schema/API/SSE/seed contract changes.**

## Problem / contract

Current JWT checks signature, audience, expiry and subject but not `iss`. Require a nonempty configured expected issuer and compare it exactly during signed-token verification. Missing, wrong, list-valued or prefix-matching issuer returns the same generic 401 as any invalid token. Never derive an authorization trust decision from the unverified token's own issuer.

Default expected issuer is `SUPABASE_URL` + `/auth/v1`; optional explicit `SUPABASE_JWT_ISSUER` supports documented custom/self-hosted issuer differences. Production override must be an HTTPS origin with `/auth/v1`, no userinfo/query/fragment/private IP; this setting is operator-controlled, never a client parameter. The signing/JWKS configuration remains independently pinned; no dynamic discovery URL is accepted from a token.

## Test cases

| ID | Expected behavior |
|---|---|
| S38-T01 | Correct synthetic issuer works through current_user; missing/wrong/list/prefix issuer rejected before endpoint work |
| S38-T02 | HS256 and ES256 both enforce issuer; algorithm/signature/audience/expiry regressions remain protected |
| S38-T03 | Default issuer comes from server Supabase URL; explicit trusted override honored, not token metadata |
| S38-T04 | Existing JWKS cache/rotation/outage behavior retained with required issuer |
| S38-T05 | Production rejects insecure/malformed issuer override; operator value/URL not token contents establishes trust |
| S38-T06 | Wrong issuer error/logs never include bearer token or private claims |

## Design plan

Make `issuer` mandatory in TokenVerifier construction. Use PyJWT's signed decode issuer validation plus required `iss`; retain explicit algorithm allowlist, audience, expiry and UUID validation. Dependency constructs verifier with trusted Settings property. Extend shared synthetic test helpers with an explicit local issuer, keeping all automated tests offline. Issuer URL override permits a valid operator configuration but does not automatically grant the signer trust for other projects.

## Implementation plan

1. Add API issuer rejection and verifier tests, confirm red on old behavior.
2. Add Settings issuer property/validated production override and pass it into verifier; require/validate `iss` in decode.
3. Update existing auth fixtures to realistic issuer-bearing tokens; retain old no-exp/no-sub/alg-none negative cases. Run current/new auth tests, full backend, static checks.
4. Document custom/local issuer setup, record checks, commit/push separately before next fix. No live auth account or provider call required.

Sources: [Supabase JWT claims](https://supabase.com/docs/guides/auth/jwts), [PyJWT issuer validation](https://pyjwt.readthedocs.io/en/stable/usage.html#issuer-claim-iss).

## Verification

Initial issuer/API tests failed on old behavior (wrong issuer accepted; issuer constructor unavailable); implementation then passed all 45 focused S38/S20 auth tests, including HS256/ES256, cache and override checks. Final full suite: 569 passed, 1 skipped, 1 expected failure; ruff/format/pyright green. Security review confirmed exact issuer matching and trusted config; no critical findings. S38 adds no Google OAuth provider or new model credentials.
