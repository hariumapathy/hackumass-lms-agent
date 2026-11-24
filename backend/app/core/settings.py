"""Application settings, read from environment variables (see repo-root .env.example)."""

import re
from functools import lru_cache
from ipaddress import ip_address
from typing import Literal, Self
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", hide_input_in_errors=True
    )

    app_env: Literal["development", "test", "production"] = "development"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwks_url: str | None = None
    database_url: str = Field(
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres", repr=False
    )
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
    # Where the agent's tools and chat history live: "mock" (S02 mock semester, in-memory chats)
    # or "db" (S01 database via DATABASE_URL, e.g. the S03 seed).
    data_source: Literal["mock", "db"] = "mock"
    embeddings_provider: Literal["gemini", "openai", "fake"] = "gemini"
    web_origin: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"  # used to build calendar feed URLs (S25)
    browser_provider: Literal["local", "hosted", "disabled"] = "local"
    canvas_base_url: str = "https://umamherst.instructure.com"

    @model_validator(mode="after")
    def production_guard(self) -> Self:
        if self.app_env != "production":
            return self
        errors: list[str] = []
        for name, expected in (
            ("data_source", "db"),
            ("chat_mode", "agent"),
            ("embeddings_provider", "gemini"),
            ("browser_provider", "disabled"),
        ):
            if getattr(self, name) != expected:
                errors.append(f"{name} must be {expected}")
        for name in ("gemini_api_key", "supabase_service_role_key"):
            value = getattr(self, name)
            if value is None or not value.get_secret_value().strip():
                errors.append(f"{name} is required")
        try:
            Fernet(self.encryption_key.get_secret_value().encode() if self.encryption_key else b"")
        except (ValueError, UnicodeError):
            errors.append("encryption_key must be a valid Fernet key")
        for name in ("web_origin", "public_api_url", "supabase_url"):
            if not _public_https(getattr(self, name), origin=name != "public_api_url"):
                kind = "URL" if name == "public_api_url" else "origin"
                errors.append(f"{name} must be a public HTTPS {kind}")
        expected_jwks = f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        if self.supabase_jwks_url != expected_jwks:
            errors.append("supabase_jwks_url must match the Supabase project's JWKS URL")
        if not _production_database(self.database_url):
            errors.append("database_url must be a non-local Postgres URL with explicit TLS")
        if errors:
            raise ValueError("Unsafe production configuration: " + "; ".join(errors))
        # Browser Origin is canonical, unlike a raw config with :443/trailing slash.
        self.web_origin = str(AnyHttpUrl(self.web_origin)).rstrip("/")
        return self


def _local_host(host: str) -> bool:
    host = host.rstrip(".").lower()
    return host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local"))


def _public_https(value: str, *, origin: bool) -> bool:
    try:
        parsed = urlsplit(value)
        # HTTP URL normalization recognizes short/octal/hex IPv4 forms too.
        host = urlsplit(str(AnyHttpUrl(value))).hostname
        host = host.rstrip(".") if host else host
        if (
            parsed.scheme != "https"
            or not host
            or _local_host(host)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (origin and parsed.path not in {"", "/"})
        ):
            return False
        _ = parsed.port  # malformed/out-of-range ports are configuration errors
        try:
            return ip_address(host).is_global
        except ValueError:
            return "." in host and not any(char.isspace() for char in value)
    except ValueError:
        return False


def _production_database(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"postgres", "postgresql"} or not host or _local_host(host):
            return False
        host = host.rstrip(".")
        try:
            if ip_address(host).is_loopback or ip_address(host).is_unspecified:
                return False
        except ValueError:
            numeric = r"(?:0[xX][0-9a-fA-F]+|[0-9]+)(?:\.(?:0[xX][0-9a-fA-F]+|[0-9]+))*"
            if re.fullmatch(numeric, host):
                return False  # OS/libpq can interpret noncanonical IPv4 as local
        if "%" in host:
            return False  # encoded host or Unix socket is not a remote DB
        _ = parsed.port
        query = parse_qs(parsed.query, keep_blank_values=True)
        # libpq query parameters override the URI authority, including Unix sockets.
        if {"host", "hostaddr", "port", "service", "servicefile", "dbname"} & query.keys():
            return False
        return query.get("sslmode") in [
            ["require"],
            ["verify-ca"],
            ["verify-full"],
        ]
    except ValueError:
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
