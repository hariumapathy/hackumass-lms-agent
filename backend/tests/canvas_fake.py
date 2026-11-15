"""Shared S11 test helpers: the hand-written Canvas fixtures + respx routes for a fake Canvas."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import respx

BASE = "https://example.instructure.com"
API = f"{BASE}/api/v1"
FIXTURE = Path(__file__).parent / "fixtures" / "canvas" / "canvas_api.json"


@cache
def _load() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def fx(name: str) -> Any:
    """A fresh copy of one fixture response."""
    return json.loads(json.dumps(_load()[name]))


def mock_canvas(router: respx.MockRouter, *, files_23456_forbidden: bool = True) -> None:
    """Every endpoint a full Canvas sync calls, answered from fixtures (path match, any query)."""
    router.get(f"{API}/users/self").respond(json=fx("users_self"))
    router.get(f"{API}/courses").respond(json=fx("courses"))
    for cid in ("12345", "23456"):
        router.get(f"{API}/courses/{cid}").respond(json=fx(f"course_{cid}"))
    router.get(f"{API}/courses/12345/assignments").respond(json=fx("assignments_12345"))
    router.get(f"{API}/courses/23456/assignments").respond(json=fx("assignments_23456"))
    router.get(f"{API}/calendar_events", params={"context_codes[]": "course_12345"}).respond(
        json=fx("calendar_events_12345")
    )
    router.get(f"{API}/calendar_events", params={"context_codes[]": "course_23456"}).respond(
        json=[]
    )
    router.get(f"{API}/announcements", params={"context_codes[]": "course_12345"}).respond(
        json=fx("announcements_12345")
    )
    router.get(f"{API}/announcements", params={"context_codes[]": "course_23456"}).respond(json=[])
    router.get(f"{API}/courses/12345/files").respond(json=fx("files_12345"))
    if files_23456_forbidden:
        router.get(f"{API}/courses/23456/files").respond(403, json=fx("forbidden"))
    else:
        router.get(f"{API}/courses/23456/files").respond(json=[])
    router.get(f"{API}/courses/23456/modules").respond(json=fx("modules_23456"))
    for fid in ("701", "702"):
        router.get(f"{API}/courses/23456/files/{fid}").respond(json=fx(f"file_23456_{fid}"))


def link_header(next_url: str | None) -> dict[str, str]:
    parts = [f'<{API}/courses?page=1&per_page=2>; rel="first"']
    if next_url:
        parts.insert(0, f'<{next_url}>; rel="next"')
    return {"Link": ", ".join(parts)}


def ok(payload: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(200, json=payload, headers=headers or {})
