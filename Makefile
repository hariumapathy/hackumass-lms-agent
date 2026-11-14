# Dev commands (S00). `just` is not required; GNU make works in Git Bash / macOS / Linux.
PNPM := npx -y pnpm@10.34.9
SUPABASE := npx -y supabase@3.1.0

.PHONY: setup db db-stop db-reset api worker web test test-backend test-web lint types

setup:
	cd backend && uv sync
	cd apps/web && $(PNPM) install

db:
	$(SUPABASE) start

db-stop:
	$(SUPABASE) stop

db-reset:
	$(SUPABASE) db reset
	@echo "Seed loading arrives with S03 (uv run app seed)."

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

worker:
	@echo "The sync worker arrives with S10."

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
	@echo "API type generation arrives with S02 (openapi-typescript)."
