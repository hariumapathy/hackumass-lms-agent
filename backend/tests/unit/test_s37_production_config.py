"""S37 startup configuration: synthetic secrets; no platform/model/network calls."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.settings import Settings

KEY = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="


def production(**overrides):
    values: dict[str, Any] = dict(
        app_env="production",
        data_source="db",
        chat_mode="agent",
        embeddings_provider="gemini",
        browser_provider="disabled",
        gemini_api_key="synthetic-model-key",
        encryption_key=KEY,
        supabase_service_role_key="synthetic-storage-key",
        supabase_url="https://project.example",
        web_origin="https://study.example",
        public_api_url="https://api.example/v1",
        supabase_jwks_url="https://project.example/auth/v1/.well-known/jwks.json",
        database_url="postgresql://user:synthetic-db-password@db.example/app?sslmode=require",
    )
    values["_env_file"] = None
    values.update(overrides)
    return Settings(**values)


def test_S37_T01_development_defaults_unchanged():
    options: dict[str, Any] = {"_env_file": None}
    settings = Settings(**options)
    assert settings.app_env == "development"
    assert settings.data_source == "mock" and settings.chat_mode == "auto"
    assert settings.browser_provider == "local"


def test_S37_T02_valid_production_without_network():
    assert production().app_env == "production"


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_source", "mock"),
        ("chat_mode", "auto"),
        ("chat_mode", "scripted"),
        ("embeddings_provider", "fake"),
        ("embeddings_provider", "openai"),
        ("browser_provider", "local"),
        ("browser_provider", "hosted"),
    ],
)
def test_S37_T03_unsafe_modes_rejected(field, value):
    with pytest.raises(ValidationError, match=field):
        production(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("gemini_api_key", ""),
        ("gemini_api_key", "   "),
        ("supabase_service_role_key", ""),
        ("encryption_key", None),
        ("encryption_key", "not-a-fernet-key"),
    ],
)
def test_S37_T04_credentials_required(field, value):
    with pytest.raises(ValidationError, match=field):
        production(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("web_origin", "http://study.example"),
        ("web_origin", "https://localhost"),
        ("web_origin", "https://127.0.0.1"),
        ("web_origin", "https://127.0.0.1."),
        ("web_origin", "https://127.1"),
        ("web_origin", "https://0177.0.0.1"),
        ("web_origin", "https://0x7f.0.0.1"),
        ("web_origin", "https://192.168.1.1."),
        ("web_origin", "https://10.0.0.1"),
        ("web_origin", "https://[::1]"),
        ("web_origin", "https://host.local"),
        ("web_origin", "https://study.example/path"),
        ("public_api_url", "https://user:secret@api.example"),
        ("public_api_url", "https://api.example?secret=bad"),
        ("public_api_url", "https://api.example#fragment"),
        ("supabase_url", "https://project.example/path"),
    ],
)
def test_S37_T05_public_urls(field, value):
    with pytest.raises(ValidationError, match=field):
        production(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("supabase_jwks_url", "https://other.example/auth/v1/.well-known/jwks.json"),
        ("database_url", "postgresql://user:secret@localhost/app?sslmode=require"),
        ("database_url", "postgresql://user:secret@db.example/app"),
        ("database_url", "postgresql://user:secret@db.example/app?sslmode=disable"),
        ("database_url", "not a database URL"),
        ("database_url", "postgresql://user:secret@127.1/app?sslmode=require"),
        ("database_url", "postgresql://user:secret@db.example/app?sslmode=require&host=localhost"),
        (
            "database_url",
            "postgresql://user:secret@db.example/app?sslmode=require&hostaddr=127.0.0.1",
        ),
        ("database_url", "postgresql://user:secret@db.example/app?sslmode=require&host=%2Ftmp"),
        ("database_url", "postgresql://user:secret@db.example/app?sslmode=require&service=local"),
    ],
)
def test_S37_T06_database_and_project_binding(field, value):
    with pytest.raises(ValidationError, match=field):
        production(**{field: value})


def test_S37_T07_no_local_fallback(monkeypatch):
    from app.connectors.browser import manager
    from app.core.errors import AppError
    from app.core.settings import get_settings

    manager.set_login_manager(None)
    for mode in ["disabled", "hosted"]:
        monkeypatch.setenv("BROWSER_PROVIDER", mode)
        get_settings.cache_clear()
        try:
            with pytest.raises(AppError, match="unavailable"):
                manager.get_login_manager()
        finally:
            manager.set_login_manager(None)
            get_settings.cache_clear()


def test_S37_T08_secret_safe_diagnostics():
    secret = "synthetic-sensitive-value"
    with pytest.raises(ValidationError) as info:
        production(database_url=f"postgresql://user:{secret}@localhost/app")
    assert secret not in str(info.value)
    assert "synthetic-db-password" not in repr(production())


def test_S37_T09_origin_normalized_for_browser_cors():
    assert production(web_origin="https://STUDY.example:443/").web_origin == "https://study.example"
