# S47 — Preserve backend configuration when launching the local web app

**Status:** Implemented and verified on review branch; unmerged. Narrow follow-up discovered during
S46 restart; spec and failing tests preceded the fix, with independent current-feature review.

## Spec and design

The web launcher owns only `apps/web/.env.local`. Existing symlinks or hardlinks at that path
must not cause it to overwrite the root `.env` or any other linked file. Build public configuration
in a private temporary file alongside the destination, then atomically rename it over the
destination link. Never copy backend keys into web config. A failed write must preserve the old
destination and clean temporary files. Keep the existing launch commands/public variables.

## Test cases

- S47-T01: synthetic root configuration remains byte-identical when web `.env.local` is a symlink
  to root `.env`; web config becomes a regular file containing only intended public variables.
- S47-T02: same behavior for a hardlink; a normal file updates and a missing file is created.
- S47-T03: replacement failure preserves the previous file/root config and removes the temp file.
- S47-T04: launch build/start behavior stays intact; private root settings never appear in the
  generated web file or command output, and generated file permissions are0600.
- S47-T05: a directory or directory symlink at the destination is rejected without moving a
  temporary file into that directory or starting the build (portable macOS/Linux behavior).

## Implementation plan

1. Use isolated temporary repositories and fake Supabase/pnpm commands to reproduce the actual
   shell launcher overwrite without real credentials, network, builds or live platforms.
2. Write/observe the failing symlink/hardlink assertions before changing the launcher.
3. Replace direct redirection with same-directory temp-file + atomic rename and cleanup trap.
4. Run focused tests, shell syntax check and backend regression/static checks; document the
   incident and local repair, commit/push separately from S46. Do not reset imports or replace
   an encryption key protecting existing ciphertext.

## Acceptance and limits

All7 synthetic actual-shell tests pass after failing first; review's directory-target edge case
also reproduced red before its fix. Full713 backend pass/1 optional Storage skip; static checks
and shell syntax pass. Prior unchanged frontend102/6 browser tests and new actual production
build/HTTP smoke pass. A real relaunch preserved the root configuration hash and left an
independent0600 web file. No application/API/schema/dependency changes.

Local incident repair verified zero connection ciphertext and zero pending encrypted payloads
before creating a fresh local encryption key; imported rows were preserved. Supplied Gemini
configuration was restored only to the ignored root file, not to the generated public web file.
This was configuration replacement where no encrypted data depended on the lost key, not
recovery of the old key. Never apply that repair to a database containing ciphertext.
