"""Agent runtime (S22): one student message -> an Agents SDK run -> S02 SSE events.

Tracing is disabled at import (our default model is Gemini; the SDK's default exporter would send
course content to OpenAI). Tools are the framework-agnostic S21 functions, adapted here.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agents import (
    Agent,
    FunctionTool,
    MaxTurnsExceeded,
    Model,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    Runner,
    Tool,
    set_tracing_disabled,
)
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent, StreamEvent
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, ValidationError

from app.agent.citations import resolve_rows, validate_citations
from app.agent.gemini import gemini_client
from app.agent.prompts import PromptContext, build_instructions
from app.agent.tools import AGENT_TOOLS
from app.agent.tools.context import RunCtx
from app.agent.tools.coverage import compute_coverage
from app.agent.tools.data import ToolData
from app.agent.tools.labels import status_label
from app.agent.tools.runner import ToolSpec, invoke, is_tool_error
from app.agent.tools.timefmt import local_time
from app.api import schemas as s
from app.core.auth import UserCtx
from app.core.clock import Clock
from app.core.settings import Settings

set_tracing_disabled(True)

log = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "gemini/gemini-default"
HISTORY_LIMIT = 12
MAX_TURNS = 8
RUN_TIMEOUT_S = 90
TOOL_TIMEOUT_S = {"fetch_latest": 25}
DEFAULT_TOOL_TIMEOUT_S = 20
DEFAULT_TIMEZONE = "America/New_York"


# --- models (S26 extends the picker) -------------------------------------------------------


class ModelUnavailable(Exception):
    pass


def model_for(choice: str | None, settings: Settings) -> tuple[Model, str]:
    """(SDK model, model id for the run log). Default: Gemini via its OpenAI-compatible API."""
    choice = choice or DEFAULT_MODEL_ID
    if choice.startswith("gemini/"):
        if not settings.gemini_api_key:
            raise ModelUnavailable(choice)
        client = gemini_client(settings.gemini_api_key.get_secret_value())
        return OpenAIChatCompletionsModel(model=settings.gemini_model, openai_client=client), choice
    if choice.startswith("openai/"):
        if not settings.openai_api_key:
            raise ModelUnavailable(choice)
        client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        return OpenAIChatCompletionsModel(model=settings.openai_model, openai_client=client), choice
    raise ModelUnavailable(choice)


def agent_available(settings: Settings) -> bool:
    return bool(settings.gemini_api_key)


# --- tools -> SDK -----------------------------------------------------------------------------


def _simplify(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_simplify(n, defs) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return _simplify(defs[node["$ref"].split("/")[-1]], defs)
    node = dict(node)
    options = node.pop("anyOf", None)
    if options:
        non_null = [o for o in options if o.get("type") != "null"]
        if len(non_null) == 1:
            node = {**_simplify(non_null[0], defs), **node}
        else:
            node["anyOf"] = _simplify(non_null, defs)
    node.pop("title", None)
    if node.get("default", ...) is None:
        node.pop("default")
    out = {k: _simplify(v, defs) if k in {"items", "properties"} else v for k, v in node.items()}
    if "properties" in out:
        out["properties"] = {k: _simplify(v, defs) for k, v in node["properties"].items()}
    return out


def _flat_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema with `$ref`s inlined, no `anyOf: [T, null]`, no titles: friendlier for Gemini
    and small models (nested models such as S24 study sets included)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    out = _simplify(schema, defs)
    out["type"] = "object"
    out.setdefault("properties", {})
    out["additionalProperties"] = False
    return out


def to_function_tool(spec: ToolSpec) -> FunctionTool:
    timeout = TOOL_TIMEOUT_S.get(spec.name, DEFAULT_TOOL_TIMEOUT_S)

    async def on_invoke(wrapper: RunContextWrapper[Any], raw_args: str) -> str:
        try:
            return await asyncio.wait_for(invoke(spec, wrapper.context, raw_args), timeout)
        except TimeoutError:
            return f"{spec.name} took too long. Answer with what you already have."

    return FunctionTool(
        name=spec.name,
        description=spec.description,
        params_json_schema=_flat_schema(spec.args_model),
        on_invoke_tool=on_invoke,
        strict_json_schema=False,
    )


def build_agent(model: Model | str, tools: Sequence[Tool], instructions: str) -> Agent[Any]:
    # include_usage: Gemini only reports token counts on streamed calls when asked (S26 costs).
    return Agent(
        name="Study assistant",
        instructions=instructions,
        tools=list(tools),
        model=model,
        model_settings=ModelSettings(include_usage=True),
    )


# --- history + event mapping (pure) -----------------------------------------------------------


def history_window(messages: list[s.Message], limit: int = HISTORY_LIMIT) -> list[dict[str, str]]:
    """Last `limit` messages, text only (citation markers stay as plain markers)."""
    return [{"role": m.role, "content": m.text} for m in messages[-limit:]]


@dataclass
class RunState:
    specs: dict[str, ToolSpec] = field(default_factory=dict)
    calls: dict[str, tuple[str, str, str, float]] = field(default_factory=dict)  # call_id ->
    # (status id, tool, label, started)
    text_parts: list[str] = field(default_factory=list)
    tool_log: list[dict[str, Any]] = field(default_factory=list)


def _label(state: RunState, tool: str, raw_args: str) -> str:
    spec = state.specs.get(tool)
    if spec is not None:
        try:
            return status_label(tool, spec.args_model.model_validate(json.loads(raw_args or "{}")))
        except (ValueError, ValidationError):
            pass
    return "Working on it…"


def map_stream_event(ev: StreamEvent, state: RunState) -> list[s.ChatEvent]:
    """SDK stream event -> immediate S02 events (text, status). Study sets and proposed blocks
    are collected by the tools in RunCtx and emitted after the answer (S02 ordering rule 3)."""
    if isinstance(ev, RawResponsesStreamEvent):
        if isinstance(ev.data, ResponseTextDeltaEvent) and ev.data.delta:
            state.text_parts.append(ev.data.delta)
            return [s.TextEvent(delta=ev.data.delta)]
        return []
    if not isinstance(ev, RunItemStreamEvent):
        return []
    raw = ev.item.raw_item
    if ev.name == "tool_called":
        call_id = str(getattr(raw, "call_id", "") or uuid4())
        tool = str(getattr(raw, "name", "tool"))
        status_id = f"t{len(state.calls) + 1}"
        label = _label(state, tool, str(getattr(raw, "arguments", "") or ""))
        state.calls[call_id] = (status_id, tool, label, time.perf_counter())
        return [s.StatusEvent(id=status_id, label=label, state="started", tool=tool)]
    if ev.name == "tool_output":
        call_id = str(raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", ""))
        if call_id not in state.calls:
            return []
        status_id, tool, label, started = state.calls[call_id]
        output = str(getattr(ev.item, "output", "") or "")
        failed = is_tool_error(output)
        state.tool_log.append(
            {"tool": tool, "ms": round((time.perf_counter() - started) * 1000), "ok": not failed}
        )
        return [
            s.StatusEvent(
                id=status_id, label=label, state="failed" if failed else "done", tool=tool
            )
        ]
    return []


# --- the run ----------------------------------------------------------------------------------

ModelFactory = Callable[[str | None], tuple[Model, str]]
ProfileLoader = Callable[[UserCtx], Awaitable[tuple[str, str | None]]]
DataFactory = Callable[[UserCtx], ToolData]


class ChatRuntime:
    def __init__(
        self,
        *,
        store: Any,
        data_factory: DataFactory,
        model_factory: ModelFactory,
        clock: Clock,
        tools: list[ToolSpec] | None = None,
        profile_loader: ProfileLoader | None = None,
    ) -> None:
        self.store = store
        self.data_factory = data_factory
        self.model_factory = model_factory
        self.clock = clock
        self.profile_loader = profile_loader
        self.tools = tools if tools is not None else list(AGENT_TOOLS)
        self.last_run: Any = None

    async def run(self, user: UserCtx, req: s.ChatRequest) -> AsyncGenerator[s.ChatEvent, None]:
        now = self.clock.now()
        tz, model_choice = DEFAULT_TIMEZONE, None
        if self.profile_loader is not None:  # DB mode: the student's timezone + model (S20)
            tz, model_choice = await self.profile_loader(user)
        data = self.data_factory(user)
        store = self.store
        conv_id = await store.ensure_conversation(
            user.user_id, req.conversation_id, req.message, now
        )
        history = await store.history(user.user_id, conv_id)
        user_msg = s.Message(id=uuid4(), role="user", text=req.message, created_at=now)
        await store.add_message(user.user_id, conv_id, user_msg)
        try:
            model, model_id = self.model_factory(model_choice)
        except ModelUnavailable:
            model, model_id = self.model_factory(None)  # chosen model has no key: default
        run_log = await store.start_run(user.user_id, conv_id, model_id)
        yield s.RunStartedEvent(
            run_id=run_log.id, conversation_id=conv_id, user_message_id=user_msg.id
        )

        connections = await data.connections()
        coverage = compute_coverage(connections, now)
        instructions = build_instructions(
            PromptContext(
                today_local=local_time(now, tz),
                timezone=tz,
                courses=await data.courses(),
                freshness=coverage.freshness,
                needs_reconnect=coverage.needs_reconnect,
            )
        )
        ctx = RunCtx(
            user_id=user.user_id, timezone=tz, clock=self.clock, data=data, block_store=store
        )
        state = RunState(specs={t.name: t for t in self.tools})
        agent = build_agent(model, [to_function_tool(t) for t in self.tools], instructions)
        result = Runner.run_streamed(
            agent,
            input=[*history_window(history), {"role": "user", "content": req.message}],  # type: ignore[list-item]
            context=ctx,
            max_turns=MAX_TURNS,
        )
        finished = False
        try:
            error: s.ErrorEvent | None = None
            try:
                async with asyncio.timeout(RUN_TIMEOUT_S):
                    async for ev in result.stream_events():
                        for out in map_stream_event(ev, state):
                            yield out
            except MaxTurnsExceeded:
                error = s.ErrorEvent(
                    code="max_turns",
                    message="That took too many steps. Try a more specific question.",
                    retryable=True,
                )
            except TimeoutError:
                error = s.ErrorEvent(
                    code="timeout", message="That took too long. Please try again.", retryable=True
                )
            except Exception as exc:  # noqa: BLE001 - provider/model errors
                log.warning(  # status code only (402 = out of credits, 429 = rate limit)
                    "agent run failed: %s status=%s",
                    type(exc).__name__,
                    getattr(exc, "status_code", None),
                )
                error = s.ErrorEvent(
                    code="model_error",
                    message="The AI service had a problem. Please try again.",
                    retryable=True,
                )
            run_log.tool_calls = state.tool_log
            usage = result.context_wrapper.usage
            run_log.input_tokens = usage.input_tokens
            run_log.output_tokens = usage.output_tokens
            run_log.model_requests = usage.requests
            self.last_run = run_log  # read by the eval runner (S26); not used by the API
            run_log.allowed_chunk_ids = set(ctx.allowed_chunk_ids)
            if error is not None:
                partial = "".join(state.text_parts)
                if partial:
                    await store.add_message(
                        user.user_id,
                        conv_id,
                        s.Message(id=uuid4(), role="assistant", text=partial, created_at=now),
                    )
                run_log.status, run_log.error = "error", error.code
                await store.finish_run(user.user_id, run_log)
                finished = True
                yield error
                return

            final = result.final_output
            final_text = final if isinstance(final, str) else "".join(state.text_parts)
            checked = validate_citations(final_text, ctx.allowed_chunk_ids, ctx.chunk_texts)
            citations = (
                resolve_rows(await data.chunks_by_id(checked.valid_ids), checked.valid_ids)
                if checked.valid_ids
                else []
            )
            for study_set in ctx.study_sets:
                await store.save_study_set(user.user_id, study_set)
                yield s.StudySetEvent(study_set=study_set)
            if ctx.proposed_blocks:
                yield s.ApprovalRequiredEvent(
                    blocks=ctx.proposed_blocks,
                    summary=ctx.block_summary
                    or (
                        "Add this study session?"
                        if len(ctx.proposed_blocks) == 1
                        else f"Add these {len(ctx.proposed_blocks)} study sessions?"
                    ),
                )
            yield s.CitationsEvent(citations=citations, dropped=checked.dropped_ids)
            message = s.Message(
                id=uuid4(),
                role="assistant",
                text=checked.clean_text,
                citations=citations,
                study_set_ids=[st.id for st in ctx.study_sets],
                block_ids=[b.id for b in ctx.proposed_blocks],
                created_at=self.clock.now(),
            )
            await store.add_message(user.user_id, conv_id, message)
            run_log.status = "done"
            run_log.turns = result.current_turn
            run_log.dropped_citations = checked.dropped_ids
            await store.finish_run(user.user_id, run_log)
            finished = True
            yield s.DoneEvent(
                run_id=run_log.id, message_id=message.id, final_text=checked.clean_text
            )
        finally:
            if not finished:  # client went away (S22-T11): stop the model, log it
                result.cancel()
                run_log.status = "cancelled"
                await store.finish_run(user.user_id, run_log)
