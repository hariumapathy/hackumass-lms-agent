"""Gemini through its OpenAI-compatible endpoint (S22 rule 8), plus one compatibility fix.

Gemini's streamed chat completions send tool-call deltas with `index: null` (or reuse one index),
so the Agents SDK merges parallel calls into one broken call (`{...}{...}`) and the provider then
rejects the next turn with 400. `GeminiClient` wraps `AsyncOpenAI` and gives every tool call its
own index, keyed by the call id. Everything else passes straight through.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


async def fix_tool_call_indexes(
    stream: AsyncIterator[ChatCompletionChunk],
) -> AsyncIterator[ChatCompletionChunk]:
    by_id: dict[str, int] = {}
    last: int | None = None
    async for chunk in stream:
        for choice in chunk.choices or []:
            deltas = (choice.delta.tool_calls if choice.delta else None) or []
            for tc in deltas:
                if tc.id:
                    tc.index = by_id.setdefault(tc.id, len(by_id))
                elif tc.index is None or by_id:
                    tc.index = last if last is not None else 0
                last = tc.index
        yield chunk


class _FixedStream:
    """Async-iterates the repaired chunks; other attributes (close, response) pass through."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        return fix_tool_call_indexes(self._stream)


class GeminiClient:
    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def _create(self, **kwargs: Any) -> Any:
        ret = await self._client.chat.completions.create(**kwargs)
        return ret if isinstance(ret, ChatCompletion) else _FixedStream(ret)


def gemini_client(api_key: str) -> Any:
    return GeminiClient(AsyncOpenAI(base_url=GEMINI_BASE_URL, api_key=api_key))
