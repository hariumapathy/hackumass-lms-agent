"""S36: sessions = conversations with their study sets; rename + delete (memory store, no LLM)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from agents.testing import ScriptedModel, assistant_message, function_call
from fastapi.testclient import TestClient

from app.agent.runtime import ChatRuntime
from app.agent.store import MemoryChatStore
from app.api import schemas as s
from app.api.routes.chat import DEMO_CONVERSATION_ID
from app.api.sse import parse_sse
from app.core.clock import FixedClock
from app.main import create_app
from tests.helpers import auth_header
from tests.runtime.test_s22_runtime import NOW, _fake_set_tool

OTHER = UUID("00000000-0000-4000-8000-0000000000b2")


def _client() -> tuple[TestClient, MemoryChatStore]:
    app = create_app()
    store = MemoryChatStore()
    model = ScriptedModel(
        [
            [function_call("create_study_set", {}, call_id="c1")],
            [assistant_message("Made you flashcards.")],
        ]
    )
    from app.agent.tools.mock_source import MockToolData

    app.state.chat_runtime = ChatRuntime(
        store=store,
        data_factory=lambda _u: MockToolData(now=NOW),
        model_factory=lambda _c: (model, "scripted/test"),
        clock=FixedClock(NOW),
        tools=[_fake_set_tool()],
    )
    return TestClient(app), store


def _chat(client: TestClient, message: str = "Flashcards for DP") -> UUID:
    with client.stream("POST", "/chat", json={"message": message}, headers=auth_header()) as r:
        events = parse_sse("".join(r.iter_text()))
    assert events[-1][0] == "done", events[-1]
    return UUID(events[0][1]["conversation_id"])


def test_s36_t01_study_set_attached_to_its_conversation() -> None:
    client, _ = _client()
    conv_id = _chat(client)
    convs = client.get("/conversations", headers=auth_header()).json()
    assert [c["id"] for c in convs] == [str(conv_id)]
    sets = convs[0]["study_sets"]
    assert len(sets) == 1 and sets[0]["type"] == "flashcards"
    assert "payload" not in sets[0]
    listed = client.get("/study-sets", headers=auth_header()).json()
    assert listed[0]["conversation_id"] == str(conv_id)


def test_s36_t02_rename() -> None:
    client, _ = _client()
    conv_id = _chat(client)
    r = client.patch(
        f"/conversations/{conv_id}", json={"title": "  Midterm prep  "}, headers=auth_header()
    )
    assert r.status_code == 200 and r.json()["title"] == "Midterm prep"
    assert client.get("/conversations", headers=auth_header()).json()[0]["title"] == "Midterm prep"
    blank = client.patch(f"/conversations/{conv_id}", json={"title": "   "}, headers=auth_header())
    assert blank.status_code == 422
    other = client.patch(
        f"/conversations/{conv_id}", json={"title": "x"}, headers=auth_header(OTHER)
    )
    assert other.status_code == 404
    unknown = client.patch(f"/conversations/{uuid4()}", json={"title": "x"}, headers=auth_header())
    assert unknown.status_code == 404


def test_s36_t03_delete_keeps_study_sets() -> None:
    client, _ = _client()
    conv_id = _chat(client)
    assert client.delete(f"/conversations/{conv_id}", headers=auth_header(OTHER)).status_code == 404
    assert client.delete(f"/conversations/{conv_id}", headers=auth_header()).status_code == 204
    assert client.get("/conversations", headers=auth_header()).json() == []
    assert client.get(f"/conversations/{conv_id}", headers=auth_header()).status_code == 404
    sets = client.get("/study-sets", headers=auth_header()).json()
    assert len(sets) == 1 and sets[0]["conversation_id"] is None
    assert client.delete(f"/conversations/{conv_id}", headers=auth_header()).status_code == 404


def test_s36_scripted_mode_demo_conversation() -> None:
    client = TestClient(create_app())  # no runtime -> scripted/demo data
    convs = client.get("/conversations", headers=auth_header()).json()
    assert convs[0]["study_sets"]  # demo conversation shows its flashcards
    r = client.patch(
        f"/conversations/{DEMO_CONVERSATION_ID}", json={"title": "New"}, headers=auth_header()
    )
    assert r.status_code == 200 and r.json()["title"] == "New"
    assert (
        client.patch(
            f"/conversations/{uuid4()}", json={"title": "x"}, headers=auth_header()
        ).status_code
        == 404
    )
    gone = client.delete(f"/conversations/{DEMO_CONVERSATION_ID}", headers=auth_header())
    assert gone.status_code == 204


async def test_s36_memory_store_isolation() -> None:
    store = MemoryChatStore()
    me = uuid4()
    now = datetime.now(UTC)
    cid = await store.ensure_conversation(me, None, "hi", now)
    assert await store.rename_conversation(OTHER, cid, "x") is None
    assert await store.delete_conversation(OTHER, cid) is False
    renamed = await store.rename_conversation(me, cid, "Mine")
    assert isinstance(renamed, s.ConversationSummary) and renamed.title == "Mine"
