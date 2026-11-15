"""Agent runtime (S22): one student message -> an Agents SDK run -> S02 SSE events.

Tracing is disabled at import (our default model is Gemini; the SDK's default exporter would send
course content to OpenAI). Tools are the framework-agnostic S21 functions, adapted here.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agents import (
    Agent,
    FunctionTool,
    MaxTurnsExceeded,
    Model,
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
from app.agent.tools import READ_TOOLS
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


def _flat_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema without `anyOf: [T, null]` and titles: friendlier for Gemini and small models."""
    schema = model.model_json_schema()
    props = {}
    for name, prop in schema.get("properties", {}).items():
        prop = dict(prop)
        options = prop.pop("anyOf", None)
        if options:
            non_null = [o for o in options if o.get("type") != "null"]
            if non_null:
                prop = {**non_null[0], **prop}
        prop.pop("title", None)
        if prop.get("default", ...) is None:
            prop.pop("default")
        props[name] = prop
    out: dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
    if schema.get("required"):
        out["required"] = schema["required"]
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
    return Agent(name="Study assistant", instructions=instructions, tools=list(tools), model=model)


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
    study_sets: list[s.StudySet] = field(default_factory=list)
    blocks: list[s.StudyBlock] = field(default_factory=list)
    block_summary: str | None = None
    tool_log: list[dict[str, Any]] = field(default_factory=list)


def _label(state: RunState, tool: str, raw_args: str) -> str:
    spec = state.specs.get(tool)
    if spec is not None:
        try:
            return status_label(tool, spec.args_model.model_validate(json.loads(raw_args or "{}")))
        except (ValueError, ValidationError):
            pass
    return "Working on it…"


def _special_outputs(tool: str, output: str, state: RunState) -> None:
    try:
        payload = json.loads(output)
    except ValueError:
        return
    if tool == "create_study_set" and isinstance(payload.get("study_set"), dict):
        state.study_sets.append(s.StudySet.model_validate(payload["study_set"]))
    elif tool == "add_study_block" and isinstance(payload.get("blocks"), list):
        state.blocks += [s.StudyBlock.model_validate(b) for b in payload["blocks"]]
        state.block_summary = payload.get("summary") or state.block_summary


def map_stream_event(ev: StreamEvent, state: RunState) -> list[s.ChatEvent]:
    """SDK stream event -> immediate S02 events (text, status). Study sets and proposed blocks
    are collected in `state` and emitted after the answer (S02 ordering rule 3)."""
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
        if not failed:
            _special_outputs(tool, output, state)
        return [
            s.StatusEvent(
                id=status_id, label=label, state="failed" if failed else "done", tool=tool
            )
        ]
    return []


# --- the run ----------------------------------------------------------------------------------

ModelFactory = Callable[[str | None], tuple[Model, str]]
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
    ) -> None:
        self.store = store
        self.data_factory = data_factory
        self.model_factory = model_factory
        self.clock = clock
        self.tools = tools if tools is not None else list(READ_TOOLS)

    async def run(self, user: UserCtx, req: s.ChatRequest) -> AsyncGenerator[s.ChatEvent, None]:
        now = self.clock.now()
        tz = DEFAULT_TIMEZONE  # profiles.timezone once S01 lands
        data = self.data_factory(user)
        store = self.store
        conv_id = await store.ensure_conversation(
            user.user_id, req.conversation_id, req.message, now
        )
        history = await store.history(user.user_id, conv_id)
        user_msg = s.Message(id=uuid4(), role="user", text=req.message, created_at=now)
        await store.add_message(user.user_id, conv_id, user_msg)
        model, model_id = self.model_factory(None)  # profiles.model_choice once S01 lands
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
        ctx = RunCtx(user_id=user.user_id, timezone=tz, clock=self.clock, data=data)
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
                log.warning("agent run failed: %s", type(exc).__name__)
                error = s.ErrorEvent(
                    code="model_error",
                    message="The AI service had a problem. Please try again.",
                    retryable=True,
                )
            run_log.tool_calls = state.tool_log
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
            for study_set in state.study_sets:
                yield s.StudySetEvent(study_set=study_set)
            if state.blocks:
                yield s.ApprovalRequiredEvent(
                    blocks=state.blocks,
                    summary=state.block_summary or f"Add {len(state.blocks)} study sessions?",
                )
            yield s.CitationsEvent(citations=citations, dropped=checked.dropped_ids)
            message = s.Message(
                id=uuid4(),
                role="assistant",
                text=checked.clean_text,
                citations=citations,
                study_set_ids=[st.id for st in state.study_sets],
                block_ids=[b.id for b in state.blocks],
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
