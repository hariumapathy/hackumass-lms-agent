"""Conversation + run persistence (S22 rule 6). `MemoryChatStore` (one process, lost on restart)
is used until S01's `conversations` / `messages` / `agent_runs` tables exist; a `DbChatStore`
with the same methods replaces it then. Every method takes `user_id` first."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.api import schemas as s


@dataclass
class RunLog:
    id: UUID
    conversation_id: UUID
    model: str
    status: str = "running"  # running | done | error | cancelled
    turns: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)  # name + duration, no content
    dropped_citations: list[int] = field(default_factory=list)
    allowed_chunk_ids: set[int] = field(default_factory=set)
    input_tokens: int = 0
    output_tokens: int = 0
    model_requests: int = 0
    error: str | None = None


class ChatStore(Protocol):
    async def ensure_conversation(
        self, user_id: UUID, conversation_id: UUID | None, first_message: str, now: datetime
    ) -> UUID: ...
    async def history(self, user_id: UUID, conversation_id: UUID) -> list[s.Message]: ...
    async def add_message(
        self, user_id: UUID, conversation_id: UUID, message: s.Message
    ) -> None: ...
    async def start_run(self, user_id: UUID, conversation_id: UUID, model: str) -> RunLog: ...
    async def finish_run(self, user_id: UUID, run: RunLog) -> None: ...
    async def conversations(self, user_id: UUID) -> list[s.ConversationSummary]: ...
    async def conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> s.ConversationDetail | None: ...
    async def rename_conversation(
        self, user_id: UUID, conversation_id: UUID, title: str
    ) -> s.ConversationSummary | None: ...
    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool: ...
    async def save_study_set(
        self, user_id: UUID, study_set: s.StudySet, conversation_id: UUID | None = None
    ) -> None: ...
    async def study_sets(self, user_id: UUID) -> list[s.StudySet]: ...
    async def save_blocks(self, user_id: UUID, blocks: list[s.StudyBlock]) -> None: ...
    async def blocks(self, user_id: UUID) -> list[s.StudyBlock]: ...
    async def propose_block(self, user_id: UUID, block: s.StudyBlock, now: datetime) -> bool: ...


class MemoryChatStore:
    def __init__(self) -> None:
        self._convs: dict[UUID, tuple[UUID, s.ConversationSummary]] = {}  # id -> (owner, summary)
        self._messages: dict[UUID, list[s.Message]] = {}
        self.runs: dict[UUID, RunLog] = {}
        self._run_owner: dict[UUID, UUID] = {}
        self._sets: dict[UUID, tuple[UUID, s.StudySet]] = {}
        self._blocks: dict[UUID, tuple[UUID, s.StudyBlock]] = {}
        self._block_created: dict[UUID, datetime] = {}

    def _owned(self, user_id: UUID, conversation_id: UUID) -> bool:
        entry = self._convs.get(conversation_id)
        return entry is not None and entry[0] == user_id

    async def ensure_conversation(
        self, user_id: UUID, conversation_id: UUID | None, first_message: str, now: datetime
    ) -> UUID:
        if conversation_id and self._owned(user_id, conversation_id):
            owner, summary = self._convs[conversation_id]
            self._convs[conversation_id] = (owner, summary.model_copy(update={"updated_at": now}))
            return conversation_id
        new_id = uuid4()  # unknown or someone else's id -> a fresh conversation
        title = first_message.strip().replace("\n", " ")[:60] or "New chat"
        self._convs[new_id] = (
            user_id,
            s.ConversationSummary(id=new_id, title=title, updated_at=now),
        )
        self._messages[new_id] = []
        return new_id

    async def history(self, user_id: UUID, conversation_id: UUID) -> list[s.Message]:
        return (
            list(self._messages.get(conversation_id, []))
            if self._owned(user_id, conversation_id)
            else []
        )

    async def add_message(self, user_id: UUID, conversation_id: UUID, message: s.Message) -> None:
        if self._owned(user_id, conversation_id):
            self._messages[conversation_id].append(message)

    async def start_run(self, user_id: UUID, conversation_id: UUID, model: str) -> RunLog:
        run = RunLog(id=uuid4(), conversation_id=conversation_id, model=model)
        self.runs[run.id] = run
        self._run_owner[run.id] = user_id
        return run

    async def finish_run(self, user_id: UUID, run: RunLog) -> None:
        if self._run_owner.get(run.id) == user_id:
            self.runs[run.id] = run

    async def conversations(self, user_id: UUID) -> list[s.ConversationSummary]:
        mine = [summary for owner, summary in self._convs.values() if owner == user_id]
        sets = await self.study_sets(user_id)
        return [
            c.model_copy(
                update={
                    "study_sets": [
                        s.StudySetSummary(**x.model_dump(exclude={"payload"}))
                        for x in sets
                        if x.conversation_id == c.id
                    ]
                }
            )
            for c in sorted(mine, key=lambda c: c.updated_at, reverse=True)
        ]

    async def rename_conversation(
        self, user_id: UUID, conversation_id: UUID, title: str
    ) -> s.ConversationSummary | None:
        if not self._owned(user_id, conversation_id):
            return None
        owner, summary = self._convs[conversation_id]
        renamed = summary.model_copy(update={"title": title})
        self._convs[conversation_id] = (owner, renamed)
        return renamed

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool:
        if not self._owned(user_id, conversation_id):
            return False
        del self._convs[conversation_id]
        self._messages.pop(conversation_id, None)
        for sid, (owner, st) in list(self._sets.items()):
            if st.conversation_id == conversation_id:
                self._sets[sid] = (owner, st.model_copy(update={"conversation_id": None}))
        return True

    async def conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> s.ConversationDetail | None:
        if not self._owned(user_id, conversation_id):
            return None
        return s.ConversationDetail(
            conversation=self._convs[conversation_id][1], messages=self._messages[conversation_id]
        )

    async def save_study_set(
        self, user_id: UUID, study_set: s.StudySet, conversation_id: UUID | None = None
    ) -> None:
        if conversation_id is not None:
            study_set = study_set.model_copy(update={"conversation_id": conversation_id})
        self._sets[study_set.id] = (user_id, study_set)

    async def study_sets(self, user_id: UUID) -> list[s.StudySet]:
        mine = [st for owner, st in self._sets.values() if owner == user_id]
        return sorted(mine, key=lambda st: st.created_at, reverse=True)

    async def save_blocks(self, user_id: UUID, blocks: list[s.StudyBlock]) -> None:
        for block in blocks:
            self._blocks[block.id] = (user_id, block)

    async def blocks(self, user_id: UUID) -> list[s.StudyBlock]:
        mine = [b for owner, b in self._blocks.values() if owner == user_id]
        return sorted(mine, key=lambda b: b.start_at)

    async def propose_block(self, user_id: UUID, block: s.StudyBlock, now: datetime) -> bool:
        from datetime import timedelta

        for bid, (owner, old) in self._blocks.items():
            fresh = self._block_created.get(bid, now) >= now - timedelta(hours=24)
            if (
                owner == user_id
                and (old.status == "approved" or (old.status == "proposed" and fresh))
                and old.start_at < block.end_at
                and old.end_at > block.start_at
            ):
                return False
        self._blocks[block.id] = (user_id, block)
        self._block_created[block.id] = now
        return True
