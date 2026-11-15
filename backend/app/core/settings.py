"""Application settings, read from environment variables (see repo-root .env.example)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwks_url: str | None = None
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    encryption_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = (
        "gemini-3.5-flash"  # behind "gemini/gemini-default" (2.5 closed to new keys)
    )
    openai_model: str = "gpt-4.1-mini"
    # auto: real agent when a model key is set, else the scripted S02 stream. scripted: always
    # the scripted stream (demo backup). agent: always the real agent.
    chat_mode: Literal["auto", "agent", "scripted"] = "auto"
    embeddings_provider: Literal["gemini", "openai", "fake"] = "gemini"
    web_origin: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"  # used to build calendar feed URLs (S25)
    browser_provider: Literal["local", "hosted"] = "local"
    canvas_base_url: str = "https://umass.instructure.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
