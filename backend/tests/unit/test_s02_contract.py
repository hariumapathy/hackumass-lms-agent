"""S02: API and streaming contract tests (stub implementation)."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import schemas as s
from app.api.sse import parse_sse, sse_event
from app.main import create_app
from tests.helpers import auth_header

AUTH = auth_header()

EXPECTED_ENDPOINTS = {
    ("get", "/health"),
    ("get", "/me"),
    ("patch", "/me"),
    ("delete", "/me/data"),
    ("get", "/models"),
    ("post", "/connections/canvas"),
    ("post", "/connections/{platform}/login"),
    ("get", "/connections/{platform}/login/{login_id}"),
    ("delete", "/connections/{platform}"),
    ("post", "/sync"),
    ("get", "/sync/status"),
    ("get", "/today"),
    ("get", "/courses"),
    ("get", "/courses/{course_id}"),
    ("get", "/items"),
    ("get", "/changes"),
    ("post", "/changes/seen"),
    ("get", "/citations"),
    ("post", "/chat"),
    ("get", "/conversations"),
    ("get", "/conversations/{conversation_id}"),
    ("get", "/study-sets"),
    ("get", "/study-sets/{study_set_id}"),
    ("post", "/study-blocks/decision"),
    ("get", "/calendar/feed"),
    ("post", "/calendar/feed/rotate"),
    ("get", "/calendar/{token}.ics"),
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_s02_t01_openapi_contains_every_endpoint(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    found = {(method, path) for path, ops in paths.items() for method in ops}
    missing = EXPECTED_ENDPOINTS - found
    assert not missing, f"missing endpoints: {sorted(missing)}"


def test_s02_t01_cli_openapi_prints_schema(capsys: pytest.CaptureFixture[str]) -> None:
    from app.cli import main as cli_main

    assert cli_main(["openapi"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert "/chat" in schema["paths"] and "ChatRequest" in schema["components"]["schemas"]


def test_s02_t02_error_envelope_401_without_token(client: TestClient) -> None:
    r = client.get("/me")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["retryable"] is False
    assert isinstance(body["error"]["message"], str)


def test_s02_t02_error_envelope_404_unknown_course(client: TestClient) -> None:
    r = client.get(f"/courses/{uuid.uuid4()}", headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_s02_t02_error_envelope_422_bad_body(client: TestClient) -> None:
    r = client.post("/chat", json={"message": ""}, headers=AUTH)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]


EVENTS: list[s.ChatEvent] = [
    s.RunStartedEvent(
        run_id=uuid.uuid4(), conversation_id=uuid.uuid4(), user_message_id=uuid.uuid4()
    ),
    s.StatusEvent(id="t1", label="Checking your deadlines…", state="started", tool="get_items"),
    s.TextEvent(delta="Midterm 1 is Nov 20 [cite:chunk_8812]"),
    s.CitationsEvent(citations=[], dropped=[77]),
    s.DoneEvent(run_id=uuid.uuid4(), message_id=uuid.uuid4(), final_text="Midterm 1 is Nov 20"),
    s.ErrorEvent(code="model_error", message="Provider failed", retryable=True),
]


@pytest.mark.parametrize("event", EVENTS, ids=lambda e: e.type)
def test_s02_t03_sse_serializer_emits_event_and_json_data(event: s.ChatEvent) -> None:
    frame = sse_event(event)
    lines = frame.split("\n")
    assert lines[0] == f"event: {event.type}"
    assert lines[1].startswith("data: ")
    assert frame.endswith("\n\n")
    data = json.loads(lines[1].removeprefix("data: "))
    assert data == json.loads(event.model_dump_json(exclude={"type"}))


def test_s02_t03_parse_sse_roundtrip() -> None:
    raw = "".join(sse_event(e) for e in EVENTS)
    parsed = parse_sse(raw)
    assert [p[0] for p in parsed] == [e.type for e in EVENTS]


def test_s02_t04_stub_chat_stream_ordering(client: TestClient) -> None:
    with client.stream(
        "POST", "/chat", json={"message": "What's due this week?"}, headers=AUTH
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        raw = "".join(r.iter_text())
    events = parse_sse(raw)
    types = [t for t, _ in events]
    assert types[0] == "run_started"
    terminal = [t for t in types if t in {"done", "error"}]
    assert terminal == [types[-1]] and len(terminal) == 1
    last_text = max(i for i, t in enumerate(types) if t == "text")
    assert types.index("citations") > last_text
    for t, data in events:  # every payload validates against its event model
        s.EVENT_MODELS[t].model_validate({"type": t, **data})


AUTH_GET_ENDPOINTS = [
    "/me",
    "/models",
    "/sync/status",
    "/today",
    "/courses",
    "/items",
    "/changes",
    "/citations?ids=8812,9930",
    "/conversations",
    "/study-sets",
    "/calendar/feed",
]


@pytest.mark.parametrize("path", AUTH_GET_ENDPOINTS)
def test_s02_stub_get_endpoints_return_contract_shapes(client: TestClient, path: str) -> None:
    r = client.get(path, headers=AUTH)
    assert r.status_code == 200, r.text


def test_s02_stub_course_detail_and_ics(client: TestClient) -> None:
    courses = client.get("/courses", headers=AUTH).json()
    detail = client.get(f"/courses/{courses[0]['id']}", headers=AUTH)
    assert detail.status_code == 200
    ics = client.get("/calendar/demo-token.ics")
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in ics.text
