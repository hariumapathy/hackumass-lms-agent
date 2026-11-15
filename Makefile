# Dev commands (S00). `just` is not required; GNU make works in Git Bash / macOS / Linux.
PNPM := npx -y pnpm@10.34.9
SUPABASE := npx -y supabase@3.1.0

.PHONY: setup db db-stop db-reset seed api worker web test test-backend test-web lint types demo-db demo-api demo-worker demo-web

setup:
	cd backend && uv sync
	cd backend && uv run playwright install chromium
	cd apps/web && $(PNPM) install

db:
	$(SUPABASE) start

db-stop:
	$(SUPABASE) stop

# Seed embeddings: fake by default (fast, no key). `make db-reset SEED_EMBEDDINGS=gemini` for the demo.
SEED_EMBEDDINGS ?= fake

db-reset:
	$(SUPABASE) db reset
	cd backend && uv run app seed --reset --embeddings $(SEED_EMBEDDINGS)

seed:
	cd backend && uv run app seed --reset --embeddings $(SEED_EMBEDDINGS)

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

worker:
	cd backend && uv run app worker

web:
	cd apps/web && $(PNPM) dev

test: test-backend test-web

test-backend:
	cd backend && uv run pytest

test-web:
	cd apps/web && $(PNPM) test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright
	cd apps/web && $(PNPM) lint && $(PNPM) typecheck

types:
	cd backend && uv run app openapi > ../apps/web/src/lib/api/openapi.json
	cd apps/web && npx openapi-typescript src/lib/api/openapi.json -o src/lib/api/schema.d.ts

# Local demo on any laptop (docs/demo-runbook.md): always the LOCAL Supabase stack, real agent.
demo-db: db
	bash scripts/demo-local.sh seed

demo-api:
	bash scripts/demo-local.sh api

demo-worker:
	bash scripts/demo-local.sh worker

demo-web:
	bash scripts/demo-local.sh web
