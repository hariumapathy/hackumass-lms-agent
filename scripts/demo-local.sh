#!/usr/bin/env bash
# Local demo on ANY laptop: everything points at the local Supabase stack (`make db`), never at
# the hosted project, whatever the root .env says. Used by `make demo-db|demo-api|demo-worker|demo-web`.
#   scripts/demo-local.sh seed     reset the local DB (migrations) + seed the demo student
#   scripts/demo-local.sh api      FastAPI on :8000 (DATA_SOURCE=db, real agent)
#   scripts/demo-local.sh worker   sync worker (Canvas / Gradescope sync after "Connect")
#   scripts/demo-local.sh web      writes apps/web/.env.local for the local stack, starts Next.js
# Needs in the root .env: GEMINI_API_KEY (agent). ENCRYPTION_KEY is generated once if empty.
set -euo pipefail
cd "$(dirname "$0")/.."
SUPABASE="npx -y supabase@3.1.0"
PNPM="npx -y pnpm@10.34.9"
cmd="${1:-}"

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }

status="$($SUPABASE status -o env 2>/dev/null || true)"
if ! grep -q '^DB_URL=' <<<"$status"; then
  echo "Local Supabase isn't running. Start Docker Desktop, then run: make db" >&2
  exit 1
fi
val() { grep "^$1=" <<<"$status" | head -1 | cut -d= -f2- | tr -d '"'; }
env_val() { grep "^$1=" .env | head -1 | cut -d= -f2- | tr -d '"' || true; }

API_URL="$(val API_URL)"
export DATABASE_URL="$(val DB_URL)"
export SUPABASE_URL="$API_URL"
export SUPABASE_JWKS_URL="$API_URL/auth/v1/.well-known/jwks.json"
export SUPABASE_JWT_SECRET="$(val JWT_SECRET)"
export SUPABASE_SERVICE_ROLE_KEY="$(val SECRET_KEY)"
export DATA_SOURCE=db
export CHAT_MODE="${CHAT_MODE:-auto}"
# The local seed uses fake embeddings; the agent must embed queries the same way.
export EMBEDDINGS_PROVIDER="${EMBEDDINGS_PROVIDER:-fake}"
export WEB_ORIGIN="${WEB_ORIGIN:-http://localhost:3000}"
export PUBLIC_API_URL="${PUBLIC_API_URL:-http://localhost:8000}"

if [ -z "$(env_val ENCRYPTION_KEY)" ] && [ "$cmd" != "web" ]; then
  key="$(cd backend && uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  if grep -q '^ENCRYPTION_KEY=' .env; then
    sed -i.bak "s|^ENCRYPTION_KEY=.*$|ENCRYPTION_KEY=$key|" .env && rm -f .env.bak
  else
    echo "ENCRYPTION_KEY=$key" >> .env
  fi
  echo "Generated ENCRYPTION_KEY in .env (the API and worker share it)."
fi

case "$cmd" in
  seed)
    $SUPABASE db reset
    cd backend && uv run app seed --reset --embeddings "$EMBEDDINGS_PROVIDER"
    ;;
  api)
    if [ -z "$(env_val GEMINI_API_KEY)" ]; then
      echo "Note: GEMINI_API_KEY is empty in .env, so chat uses the scripted demo answer." >&2
    fi
    # No --reload: on Windows it can hang or leave an old server on :8000 (see devlog).
    cd backend && exec uv run app serve --port 8000
    ;;
  worker)
    cd backend && exec uv run app worker
    ;;
  web)
    cat > apps/web/.env.local <<EOF
# Written by scripts/demo-local.sh for the LOCAL Supabase stack. Delete to go back to mocks.
NEXT_PUBLIC_SUPABASE_URL=$API_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$(val PUBLISHABLE_KEY)
NEXT_PUBLIC_API_URL=$PUBLIC_API_URL
NEXT_PUBLIC_API_MOCKS=0
NEXT_PUBLIC_GOOGLE_SIGN_IN_ENABLED=0
EOF
    echo "Wrote apps/web/.env.local. Sign-in emails arrive at $(val MAILPIT_URL)"
    cd apps/web
    $PNPM build
    exec $PNPM start
    ;;
  *)
    echo "usage: scripts/demo-local.sh seed|api|worker|web" >&2
    exit 2
    ;;
esac
