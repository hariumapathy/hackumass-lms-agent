"""Framework-agnostic tool invocation (S21 rules 3, 9, 11, 12).

`invoke(spec, ctx, raw_json)` has the shape the Agents SDK's FunctionTool wants
(`on_invoke_tool(ctx, args_json) -> str`); S22 adds the thin adapter. Bad arguments or a crashing
tool come back to the model as a readable string, never as an exception.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent.tools.context import RunCtx
from app.agent.tools.results import (
    ToolResult,
    collect_chunk_ids,
    collect_chunk_texts,
    truncate_result,
)

log = logging.getLogger(__name__)

ToolFn = Callable[[RunCtx, Any], Awaitable[ToolResult]]


class ToolRejected(Exception):
    """Raised by a tool for a problem the model can fix; its message goes back to the model."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    fn: ToolFn
    description: str = ""


def is_tool_error(output: str) -> bool:
    """Successful tool results are JSON objects; errors are plain sentences."""
    return not output.lstrip().startswith("{")


def _describe(err: ValidationError) -> str:
    parts = []
    for e in err.errors():
        where = ".".join(str(p) for p in e.get("loc", ())) or "arguments"
        parts.append(f"{where}: {e.get('msg', 'invalid')}")
    return "; ".join(parts)


async def invoke(spec: ToolSpec, ctx: RunCtx, raw_args: str) -> str:
    try:
        args = spec.args_model.model_validate(json.loads(raw_args or "{}"))
    except json.JSONDecodeError:
        return f"Invalid arguments for {spec.name}: arguments must be a JSON object."
    except ValidationError as err:
        return f"Invalid arguments for {spec.name}: {_describe(err)}. Fix them and try again."
    try:
        result = await spec.fn(ctx, args)
    except ToolRejected as err:
        return f"{spec.name} rejected: {err} Fix it and try again."
    except Exception:  # noqa: BLE001 - the model gets a readable error; details go to our logs
        log.exception("tool %s failed", spec.name)
        return f"{spec.name} failed. Try again once, or answer with what you already have."
    result = truncate_result(result)
    ctx.allowed_chunk_ids |= collect_chunk_ids(result)
    ctx.chunk_texts.update(collect_chunk_texts(result))
    return result.model_dump_json(exclude_none=True)
