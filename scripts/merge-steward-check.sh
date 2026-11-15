#!/usr/bin/env bash
# Merge steward: cheap status check (no changes made). Prints one line per dev branch:
#   <branch> ahead=<n> behind=<n> conflicts=<yes|no> pr=<number|none> ci=<pass|fail|pending|none> head=<sha> "<subject>"
# Used by docs/handoff/merge-steward.md every tick.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git fetch -q --all --prune
BRANCHES="${STEWARD_BRANCHES:-dev/hari dev/neal dev/soumith}"
for b in $BRANCHES; do
  ref="origin/$b"
  git rev-parse -q --verify "$ref" >/dev/null || { echo "$b missing"; continue; }
  ahead=$(git rev-list --count "origin/main..$ref")
  behind=$(git rev-list --count "$ref..origin/main")
  conflicts=no
  if [ "$ahead" -gt 0 ]; then
    base=$(git merge-base origin/main "$ref")
    if git merge-tree --write-tree --name-only origin/main "$ref" >/tmp/steward-mt.$$ 2>&1; then :; else conflicts=yes; fi
    rm -f /tmp/steward-mt.$$
    : "$base"
  fi
  pr=$(gh pr list --base main --state open --json number,headRefName \
        --jq "map(select(.headRefName==\"$b\" or .headRefName==\"merge/${b#dev/}\"))[0].number // \"none\"" 2>/dev/null || echo none)
  ci=none
  if [ "$pr" != "none" ]; then
    checks=$(gh pr checks "$pr" 2>/dev/null || true)
    if echo "$checks" | grep -q "fail"; then ci=fail
    elif echo "$checks" | grep -qE "pending|queued|in_progress"; then ci=pending
    elif echo "$checks" | grep -q "pass"; then ci=pass; fi
  fi
  head=$(git log -1 --format='%h' "$ref"); subject=$(git log -1 --format='%s' "$ref" | cut -c1-70)
  echo "$b ahead=$ahead behind=$behind conflicts=$conflicts pr=$pr ci=$ci head=$head \"$subject\""
done
