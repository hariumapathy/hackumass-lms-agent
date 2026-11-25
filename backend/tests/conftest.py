"""Test-wide setup: never read the developer's real .env auth settings, never hit the network."""

import asyncio
import os
import sys
from collections.abc import Iterator

import pytest

from tests.helpers import TEST_JWT_SECRET

# Tests never touch the hosted project: local Supabase DB unless TEST_DATABASE_URL says otherwise.
LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
# Set at import time too: some modules read settings when imported (e.g. the Procrastinate app in
# app.sync.jobs builds its connector from DATABASE_URL), before any fixture runs.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", LOCAL_DB)
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
# Never hand the hosted project's secret key to tests; use the local stack's key if provided
# (`supabase status` prints it), else storage tests skip.
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = os.environ.get("TEST_SUPABASE_SERVICE_ROLE_KEY", "")


def pytest_asyncio_loop_factories(config, item):  # noqa: ANN001, ANN201, ARG001
    """psycopg async can't use Windows' default Proactor loop; use a selector loop there."""
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}


@pytest.fixture(autouse=True)
def _test_auth_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from app.api import deps
    from app.core.settings import get_settings

    # Env vars beat the .env file in pydantic-settings, so these override a developer's .env.
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SUPABASE_JWKS_URL", "")
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "")
    # Tests never call real LLMs: no model keys, so POST /chat uses the scripted stream.
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("CHAT_MODE", "auto")
    monkeypatch.setenv("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", LOCAL_DB))
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
    yield
    get_settings.cache_clear()
    deps.get_verifier.cache_clear()
