"""Server-Sent Events framing for the chat stream (S02)."""

import json
from typing import Any

from pydantic import BaseModel


def sse_event(event: BaseModel) -> str:
    """Serialize a chat event model as one SSE frame.

    The model's `type` field becomes the SSE `event:` name and is not repeated in `data`.
    """
    event_type = str(event.model_dump(include={"type"})["type"])
    data = event.model_dump_json(exclude={"type"})
    return f"event: {event_type}\ndata: {data}\n\n"


def parse_sse(raw: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse a complete SSE text into (event_type, data) pairs. Used by tests and evals."""
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in raw.replace("\r\n", "\n").split("\n\n"):
        if not frame.strip():
            continue
        event_type = "message"
        data_lines: list[str] = []
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event_type = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        events.append((event_type, json.loads("\n".join(data_lines)) if data_lines else {}))
    return events
