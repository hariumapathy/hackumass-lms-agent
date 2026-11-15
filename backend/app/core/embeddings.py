"""Embedding providers (S12 interface; used first by the S03 seed loader).

- `FakeEmbeddings`: deterministic vectors from a hash of the text (tests, CI, quick local seed).
- `GeminiEmbeddings` (default): `gemini-embedding-001` through Google's OpenAI-compatible endpoint
  at 1536 dims, L2-normalized (Google only pre-normalizes 3072-dim output).
Never mix providers in one database: switching provider means re-embedding everything.
"""

import asyncio
import hashlib
import math
import random
from typing import Protocol

import httpx

from app.core.settings import Settings, get_settings

EMBEDDING_DIM = 1536
BATCH_SIZE = 100


class EmbeddingsConfigError(RuntimeError):
    """Provider misconfigured (e.g. missing API key). Raised before anything is written."""


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class FakeEmbeddings:
    """Same text -> same vector; 1536 dims; unit length. No network."""

    name = "fake"
    dim = EMBEDDING_DIM

    def embed_one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        return _normalize([rng.gauss(0.0, 1.0) for _ in range(self.dim)])

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]


class GeminiEmbeddings:
    name = "gemini"
    dim = EMBEDDING_DIM
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    model = "gemini-embedding-001"

    def __init__(
        self, api_key: str, client: httpx.AsyncClient | None = None, max_retries: int = 4
    ) -> None:
        self._key = api_key
        self._client = client
        self._max_retries = max_retries

    async def _post(self, client: httpx.AsyncClient, batch: list[str]) -> list[list[float]]:
        delay = 1.0
        for attempt in range(self._max_retries + 1):
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._key}"},
                json={"model": self.model, "input": batch, "dimensions": self.dim},
                timeout=60,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self._max_retries:
                    resp.raise_for_status()
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            data = resp.json()["data"]
            # Gemini's OpenAI-compatible endpoint omits `index` (results come back in input
            # order); OpenAI includes it. Sort only when present.
            if all("index" in d for d in data):
                data = sorted(data, key=lambda d: d["index"])
            if len(data) != len(batch):
                raise RuntimeError(f"embedding count mismatch: {len(data)} for {len(batch)} texts")
            return [_normalize(d["embedding"]) for d in data]
        raise RuntimeError("unreachable")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client or httpx.AsyncClient()
        try:
            out: list[list[float]] = []
            for i in range(0, len(texts), BATCH_SIZE):
                out.extend(await self._post(client, texts[i : i + BATCH_SIZE]))
            return out
        finally:
            if self._client is None:
                await client.aclose()


def get_embeddings(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.embeddings_provider == "fake":
        return FakeEmbeddings()
    if settings.embeddings_provider == "gemini":
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise EmbeddingsConfigError(
                "EMBEDDINGS_PROVIDER=gemini needs GEMINI_API_KEY in .env "
                "(or set EMBEDDINGS_PROVIDER=fake for local testing)."
            )
        return GeminiEmbeddings(settings.gemini_api_key.get_secret_value())
    raise EmbeddingsConfigError(
        f"EMBEDDINGS_PROVIDER={settings.embeddings_provider} is not supported yet (use gemini/fake)"
    )


def to_pgvector(vec: list[float]) -> str:
    """Text form accepted by `%s::extensions.vector`."""
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"
