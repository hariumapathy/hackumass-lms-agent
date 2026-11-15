"""`DbChatStore`: the `ChatStore` interface (store.py) on the S01 tables."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.agent.store import RunLog
from app.api import schemas as s
from app.db.repositories import chat as repo

ConnectionFactory = Callable[[], AbstractAsyncContextManager[Any]]


def _message(row: dict[str, Any]) -> s.Message:
    content = row["content"] or {}
    return s.Message(
        id=row["id"],
        role=row["role"],
        text=content.get("text", ""),
        citations=content.get("citations", []),
        study_set_ids=content.get("study_set_ids", []),
        block_ids=content.get("block_ids", []),
        created_at=row["created_at"],
    )


class DbChatStore:
    def __init__(self, connection: ConnectionFactory) -> None:
        self._connection = connection

    async def ensure_conversation(
        self, user_id: UUID, conversation_id: UUID | None, first_message: str, now: datetime
    ) -> UUID:
        async with self._connection() as conn:
            if conversation_id and await repo.get_conversation(conn, user_id, conversation_id):
                await repo.touch_conversation(conn, user_id, conversation_id, now)
                return conversation_id
            title = first_message.strip().replace("\n", " ")[:60] or "New chat"
            return await repo.create_conversation(conn, user_id, title, now)

    async def history(self, user_id: UUID, conversation_id: UUID) -> list[s.Message]:
        async with self._connection() as conn:
            return [_message(r) for r in await repo.list_messages(conn, user_id, conversation_id)]

    async def add_message(self, user_id: UUID, conversation_id: UUID, message: s.Message) -> None:
        content = {
            "text": message.text,
            "citations": [c.model_dump(mode="json") for c in message.citations],
            "study_set_ids": [str(x) for x in message.study_set_ids],
            "block_ids": [str(x) for x in message.block_ids],
        }
        async with self._connection() as conn:
            await repo.insert_message(
                conn,
                user_id,
                conversation_id,
                message.id,
                message.role,
                content,
                message.created_at,
            )

    async def start_run(self, user_id: UUID, conversation_id: UUID, model: str) -> RunLog:
        run = RunLog(id=uuid4(), conversation_id=conversation_id, model=model)
        async with self._connection() as conn:
            await repo.insert_run(conn, user_id, run.id, conversation_id, model)
        return run

    async def finish_run(self, user_id: UUID, run: RunLog) -> None:
        # agent_runs.status allows running|done|error: a cancelled run is an error "cancelled".
        status = "done" if run.status == "done" else "error"
        error = run.error or ("cancelled" if run.status == "cancelled" else None)
        async with self._connection() as conn:
            await repo.finish_run(
                conn,
                user_id,
                run.id,
                status,
                run.turns,
                run.tool_calls,
                sorted(run.allowed_chunk_ids),
                error,
            )

    async def conversations(self, user_id: UUID) -> list[s.ConversationSummary]:
        async with self._connection() as conn:
            rows = await repo.list_conversations(conn, user_id)
        return [s.ConversationSummary.model_validate(r) for r in rows]

    async def conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> s.ConversationDetail | None:
        async with self._connection() as conn:
            row = await repo.get_conversation(conn, user_id, conversation_id)
            if row is None:
                return None
            messages = [
                _message(r) for r in await repo.list_messages(conn, user_id, conversation_id)
            ]
        return s.ConversationDetail(
            conversation=s.ConversationSummary.model_validate(row), messages=messages
        )

    async def save_study_set(self, user_id: UUID, study_set: s.StudySet) -> None:
        async with self._connection() as conn:
            await repo.insert_study_set(conn, user_id, study_set.model_dump(mode="json"))

    async def study_sets(self, user_id: UUID) -> list[s.StudySet]:
        async with self._connection() as conn:
            rows = await repo.list_study_sets(conn, user_id)
        return [s.StudySet.model_validate(r) for r in rows]

    async def save_blocks(self, user_id: UUID, blocks: list[s.StudyBlock]) -> None:
        async with self._connection() as conn:
            await repo.insert_blocks(conn, user_id, [b.model_dump(mode="json") for b in blocks])

    async def blocks(self, user_id: UUID) -> list[s.StudyBlock]:
        async with self._connection() as conn:
            rows = await repo.list_blocks(conn, user_id)
        return [s.StudyBlock.model_validate(r) for r in rows]

    async def propose_block(self, user_id: UUID, block: s.StudyBlock, now: datetime) -> bool:
        from app.db.repositories.calendar import propose

        async with self._connection() as conn:
            return await propose(conn, user_id, block, now)
