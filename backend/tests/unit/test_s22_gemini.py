"""S22: Gemini OpenAI-compatible stream fix (tool calls arrive with index=null)."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from app.agent.gemini import fix_tool_call_indexes


def _chunk(tool_calls: list[dict]) -> Any:
    """Like the SDK's unvalidated stream chunks (that's how index=None gets through)."""
    calls = [
        SimpleNamespace(index=c["index"], id=c.get("id"), function=SimpleNamespace(**c["function"]))
        for c in tool_calls
    ]
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(tool_calls=calls))])


async def _stream(chunks: list[Any]) -> AsyncIterator[Any]:
    for c in chunks:
        yield c


def _call(call_id: str | None, name: str | None, args: str, index: int | None = None) -> dict:
    fn: dict = {"arguments": args}
    if name:
        fn["name"] = name
    out: dict = {"index": index, "function": fn, "type": "function"}
    if call_id:
        out["id"] = call_id
    return out


async def test_s22_gemini_parallel_calls_get_separate_indexes() -> None:
    chunks = [
        _chunk([_call("a", "get_items", '{"type":"exam"}'), _call("b", "search_materials", "{}")]),
    ]
    fixed = [c async for c in fix_tool_call_indexes(_stream(chunks))]
    indexes = [tc.index for tc in fixed[0].choices[0].delta.tool_calls or []]
    assert indexes == [0, 1]


async def test_s22_gemini_continuation_deltas_keep_their_call_index() -> None:
    chunks = [
        _chunk([_call("a", "get_items", '{"type":')]),
        _chunk([_call(None, None, '"exam"}')]),
        _chunk([_call("b", "get_changes", "{}", index=0)]),  # reused index 0 for a new call
    ]
    fixed = [c async for c in fix_tool_call_indexes(_stream(chunks))]
    got = [tc.index for c in fixed for tc in c.choices[0].delta.tool_calls or []]
    assert got == [0, 0, 1]


async def test_s22_gemini_openai_style_stream_unchanged() -> None:
    chunks = [_chunk([_call("a", "get_items", "{}", index=0)]), _chunk([_call(None, None, "", 0)])]
    fixed = [c async for c in fix_tool_call_indexes(_stream(chunks))]
    assert [tc.index for c in fixed for tc in c.choices[0].delta.tool_calls or []] == [0, 0]
