"""S03 seed loader: a realistic fake semester for one student (docs/specs/S03-seed-data.md).

Fixtures live in `supabase/seed/` (`semester.json` + `courses/<key>.json`). Dates are relative to
load time and resolved in the profile timezone (`seed_dates.py`). IDs are deterministic:
`uuid5(NAMESPACE_URL, "<namespace>/<kind>/<key>")` with namespace `hackumass-mock`, the same IDs
as `app/api/mock_data.py`, so mock mode and seeded mode show the same courses, items and posts.

Until S12's chunker lands, each page / slide / transcript window / post becomes one chunk with the
S12 context header. Embeddings come from `app.core.embeddings` (fake for tests).
"""

import json
import math
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.core.embeddings import EmbeddingProvider, to_pgvector
from app.core.hashing import content_hash
from app.db.repositories.profiles import delete_user_data
from app.db.seed_dates import resolve

SEED_DIR = Path(__file__).resolve().parents[3] / "supabase" / "seed"
DEFAULT_NAMESPACE = "hackumass-mock"
DEMO_EMAIL = "demo@example.com"

COURSE_HOST = {
    "canvas": "https://example.instructure.com/courses/{course}",
    "gradescope": "https://example.gradescope.com/courses/{course}",
    "echo360": "https://example.echo360.com/section/{course}",
    "piazza": "https://example.piazza.com/class/{course}",
}
CITATION_KIND = {
    "file": "slides",
    "syllabus": "syllabus",
    "page": "page",
    "transcript": "transcript",
}
_TEMPLATE = re.compile(r"\{\{(when|cite):([^}]+)\}\}")


class SeedError(RuntimeError):
    pass


class SeedExistsError(SeedError):
    pass


def seed_id(namespace: str, name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{namespace}/{name}")


def approx_tokens(text: str) -> int:
    """~4 characters per token. S12 replaces this with tiktoken (cl100k_base)."""
    return max(1, math.ceil(len(text) / 4))


def mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


# ---------------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------------
def load_fixtures(seed_dir: Path = SEED_DIR) -> dict[str, Any]:
    """Read + validate fixtures. Raises SeedError listing every bad reference."""
    semester = json.loads((seed_dir / "semester.json").read_text(encoding="utf-8"))
    courses = {c["key"]: c for c in semester["courses"]}
    errors: list[str] = []
    content: dict[str, Any] = {}
    for path in sorted((seed_dir / "courses").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["course"] not in courses:
            errors.append(f"{path.name}: unknown course {data['course']!r}")
            continue
        content[data["course"]] = data
    semester["content"] = content

    item_keys: dict[str, str] = {}
    post_keys: dict[str, str] = {}
    refs: set[str] = set()
    for ck, data in content.items():
        for it in data.get("items", []):
            if it["key"] in item_keys:
                errors.append(f"duplicate item key {it['key']!r}")
            item_keys[it["key"]] = ck
            for p in it.get("sources", []):
                if p not in courses[ck]["platforms"]:
                    errors.append(f"item {it['key']}: course {ck} is not on {p}")
        for po in data.get("posts", []):
            if po["key"] in post_keys:
                errors.append(f"duplicate post key {po['key']!r}")
            post_keys[po["key"]] = ck
            refs.add(f"{ck}/post:{po['key']}")
        for m in data.get("materials", []):
            n = len(m.get("cues") or m.get("pages") or [])
            refs.update(f"{ck}/{m['key']}#{i}" for i in range(1, n + 1))
    semester["_item_course"] = item_keys
    semester["_post_course"] = post_keys

    def check_ref(where: str, ref: str) -> None:
        if ref not in refs:
            errors.append(f"{where}: unknown reference {ref!r}")

    for ch in semester.get("changes", []):
        kind, key = ch["entity"].split("/", 1)
        if (kind == "item" and key not in item_keys) or (kind == "post" and key not in post_keys):
            errors.append(f"change {ch['key']}: unknown {ch['entity']!r}")
    for ss in semester.get("study_sets", []):
        if ss.get("course") and ss["course"] not in courses:
            errors.append(f"study set {ss['key']}: unknown course {ss['course']!r}")
        for entry in _payload_entries(ss["payload"]):
            for ref in entry.get("refs", []):
                check_ref(f"study set {ss['key']}", ref)
    for b in semester.get("study_blocks", []):
        if b.get("course") and b["course"] not in courses:
            errors.append(f"study block {b['key']}: unknown course {b['course']!r}")
        if b.get("item") and b["item"] not in item_keys:
            errors.append(f"study block {b['key']}: unknown item {b['item']!r}")
    for conv in semester.get("conversations", []):
        for msg in conv["messages"]:
            for kind, arg in _TEMPLATE.findall(msg["text"]):
                if kind == "cite":
                    check_ref(f"conversation {conv['key']}", arg)
    for data in content.values():
        for po in data.get("posts", []):
            for kind, arg in _TEMPLATE.findall(po["body"]):
                if kind == "when" and arg not in item_keys:
                    errors.append(f"post {po['key']}: unknown item {arg!r}")
    if errors:
        raise SeedError("Seed fixtures have problems:\n- " + "\n- ".join(errors))
    return semester


def _payload_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out += payload.get("cards", [])
    out += payload.get("questions", [])
    for day in payload.get("days", []):
        out += day.get("tasks", [])
    return out


# ---------------------------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------------------------
@dataclass
class _ChunkDraft:
    ref: str
    course_key: str
    material_key: str | None
    post_key: str | None
    text: str
    page: int | None = None
    start_s: int | None = None
    end_s: int | None = None


@dataclass
class SeedResult:
    user_id: UUID
    counts: dict[str, int] = field(default_factory=dict)


class _Loader:
    def __init__(
        self,
        conn: AsyncConnection[Any],
        user_id: UUID,
        fx: dict[str, Any],
        now: datetime,
        namespace: str,
    ) -> None:
        self.conn, self.user_id, self.fx, self.ns = conn, user_id, fx, namespace
        self.now = now.astimezone(UTC).replace(microsecond=0)
        self.tz = fx["profile"].get("timezone", "America/New_York")
        self.courses = {c["key"]: c for c in fx["courses"]}
        self.item_due: dict[str, datetime | None] = {}
        self.post_body: dict[str, str] = {}
        self.chunk_ids: dict[str, int] = {}
        self.chunk_info: dict[int, dict[str, Any]] = {}
        self.counts: dict[str, int] = {}

    def id(self, name: str) -> UUID:
        return seed_id(self.ns, name)

    def at(self, expr: str) -> datetime:
        return resolve(expr, self.now, self.tz)

    def bump(self, table: str, n: int = 1) -> None:
        self.counts[table] = self.counts.get(table, 0) + n

    async def exec(self, sql: str, params: tuple[Any, ...]) -> Any:
        cur = await self.conn.execute(sql, params)  # type: ignore[arg-type]
        return await cur.fetchone() if cur.description else None

    def when_text(self, item_key: str) -> str:
        due = self.item_due[item_key]
        assert due is not None
        local = due.astimezone(ZoneInfo(self.tz))
        hour = local.hour % 12 or 12
        minute = f":{local.minute:02d}" if local.minute else ""
        ampm = "AM" if local.hour < 12 else "PM"
        return f"{local:%A %b} {local.day} at {hour}{minute} {ampm}"  # portable (no %-d)

    def render(self, text: str) -> str:
        def sub(m: re.Match[str]) -> str:
            kind, arg = m.group(1), m.group(2)
            if kind == "when":
                return self.when_text(arg)
            return f"[cite:chunk_{self.chunk_ids[arg]}]"

        return _TEMPLATE.sub(sub, text)

    # --- top-level tables --------------------------------------------------------------------
    async def profile_and_connections(self) -> None:
        p = self.fx["profile"]
        await self.exec(
            "insert into profiles (user_id, display_name, timezone, model_choice) "
            "values (%s, %s, %s, %s) on conflict (user_id) do update set "
            "display_name = excluded.display_name, timezone = excluded.timezone, "
            "model_choice = excluded.model_choice",
            (self.user_id, p.get("display_name"), self.tz, p.get("model_choice")),
        )
        self.bump("profiles")
        for c in self.fx["connections"]:
            last = self.at(c["last_sync"]) if c.get("last_sync") else None
            await self.exec(
                "insert into connections (id, user_id, platform, status, expires_at, "
                "last_sync_at, last_error, account_label) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"connection/{c['platform']}"),
                    self.user_id,
                    c["platform"],
                    c["status"],
                    self.at(c["expires"]) if c.get("expires") else None,
                    last,
                    c.get("last_error"),
                    c.get("account_label"),
                ),
            )
            self.bump("connections")
            ok = c["status"] == "active"
            await self.exec(
                "insert into sync_runs (id, user_id, platform, scope, trigger, status, stats, "
                "error, queued_at, started_at, finished_at) "
                "values (%s,%s,%s,%s,'schedule',%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"syncrun/{c['platform']}"),
                    self.user_id,
                    c["platform"],
                    Jsonb({"kind": "full"}),
                    "succeeded" if ok else "needs_reconnect",
                    Jsonb({"new": 0, "changed": 0, "unchanged": 42 if ok else 0, "removed": 0}),
                    None if ok else c.get("last_error"),
                    last,
                    last,
                    last,
                ),
            )
            self.bump("sync_runs")
        await self.exec(
            "insert into calendar_feeds (user_id, secret_token) values (%s, %s)",
            (self.user_id, secrets.token_urlsafe(24)),
        )
        self.bump("calendar_feeds")

    async def courses_and_links(self) -> None:
        synced = self.now - timedelta(minutes=12)
        for c in self.fx["courses"]:
            await self.exec(
                "insert into courses (id, user_id, name, code, term, color) "
                "values (%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"course/{c['key']}"),
                    self.user_id,
                    c["name"],
                    c["code"],
                    self.fx["term"],
                    c.get("color"),
                ),
            )
            self.bump("courses")
            for platform in c["platforms"]:
                await self.exec(
                    "insert into course_links (user_id, course_id, platform, platform_id, "
                    "source_url, content_hash, last_synced_at) values (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self.user_id,
                        self.id(f"course/{c['key']}"),
                        platform,
                        f"seed-{c['key']}",
                        COURSE_HOST[platform].format(course=c["key"]),
                        content_hash({"name": c["name"], "code": c["code"]}),
                        synced,
                    ),
                )
                self.bump("course_links")

    async def items(self) -> None:
        changed = {
            ch["entity"].split("/", 1)[1]
            for ch in self.fx.get("changes", [])
            if ch["entity"].startswith("item/")
        }
        for ck, data in self.fx["content"].items():
            for it in data.get("items", []):
                due = self.at(it["due"]) if it.get("due") else None
                self.item_due[it["key"]] = due
                status = it.get("status") or ("changed" if it["key"] in changed else "active")
                item_id = self.id(f"item/{it['key']}")
                await self.exec(
                    "insert into items (id, user_id, course_id, type, title, description, "
                    "due_at, points, status, updated_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        item_id,
                        self.user_id,
                        self.id(f"course/{ck}"),
                        it["type"],
                        it["title"],
                        it.get("description"),
                        due,
                        it.get("points"),
                        status,
                        self.now,
                    ),
                )
                self.bump("items")
                for platform in it["sources"]:
                    host = COURSE_HOST[platform].format(course=ck)
                    raw = {"title": it["title"], "due_at": due, "points": it.get("points")}
                    await self.exec(
                        "insert into item_sources (user_id, item_id, course_id, raw_title, "
                        "raw_due_at, raw, platform, platform_id, source_url, content_hash, "
                        "source_updated_at, last_synced_at, status) "
                        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            self.user_id,
                            item_id,
                            self.id(f"course/{ck}"),
                            it["title"],
                            due,
                            Jsonb({**raw, "due_at": due.isoformat() if due else None}),
                            platform,
                            f"{ck}-{it['key']}",
                            f"{host}/assignments/{it['key']}",
                            content_hash(raw),
                            self.now - timedelta(days=1),
                            self.now - timedelta(minutes=12),
                            status,
                        ),
                    )
                    self.bump("item_sources")

    async def posts(self) -> list[_ChunkDraft]:
        drafts: list[_ChunkDraft] = []
        changed = {
            ch["entity"].split("/", 1)[1]
            for ch in self.fx.get("changes", [])
            if ch["entity"].startswith("post/")
        }
        for ck, data in self.fx["content"].items():
            code = self.courses[ck]["code"]
            for po in data.get("posts", []):
                body = self.render(po["body"])
                self.post_body[po["key"]] = body
                platform = "piazza" if po["kind"] == "piazza" else "canvas"
                url = (
                    f"https://example.piazza.com/class/{ck}/post/{po['key']}"
                    if platform == "piazza"
                    else f"{COURSE_HOST['canvas'].format(course=ck)}/discussion_topics/{po['key']}"
                )
                posted = self.at(po["posted"])
                await self.exec(
                    "insert into posts (id, user_id, course_id, kind, title, body, author, "
                    "posted_at, platform, platform_id, source_url, content_hash, "
                    "source_updated_at, last_synced_at, status) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self.id(f"post/{po['key']}"),
                        self.user_id,
                        self.id(f"course/{ck}"),
                        po["kind"],
                        po["title"],
                        body,
                        po.get("author"),
                        posted,
                        platform,
                        f"{ck}-{po['key']}",
                        url,
                        content_hash({"title": po["title"], "body": body}),
                        posted,
                        self.now - timedelta(minutes=12),
                        "changed" if po["key"] in changed else "active",
                    ),
                )
                self.bump("posts")
                label = "Piazza" if po["kind"] == "piazza" else "Announcement"
                drafts.append(
                    _ChunkDraft(
                        ref=f"{ck}/post:{po['key']}",
                        course_key=ck,
                        material_key=None,
                        post_key=po["key"],
                        text=f"[{code} · {label} · {po['title']}]\n{po['title']}\n{body}",
                    )
                )
        return drafts

    async def materials(self) -> list[_ChunkDraft]:
        drafts: list[_ChunkDraft] = []
        for ck, data in self.fx["content"].items():
            code = self.courses[ck]["code"]
            for m in data.get("materials", []):
                pages: list[str] = m.get("pages") or []
                cues: list[dict[str, Any]] = m.get("cues") or []
                is_transcript = m["kind"] == "transcript"
                platform = "echo360" if is_transcript else "canvas"
                if is_transcript:
                    url = f"https://example.echo360.com/lesson/{m['key']}"
                elif m["kind"] == "page":
                    url = f"{COURSE_HOST['canvas'].format(course=ck)}/pages/{m['key']}"
                else:
                    url = f"{COURSE_HOST['canvas'].format(course=ck)}/files/{m['key']}"
                default_status = "done" if (pages or cues) else "pending"
                await self.exec(
                    "insert into materials (id, user_id, course_id, kind, title, mime_type, "
                    "page_count, duration_s, recorded_at, version, processing_status, "
                    "processing_error, platform, platform_id, source_url, content_hash, "
                    "source_updated_at, last_synced_at) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        self.id(f"material/{ck}/{m['key']}"),
                        self.user_id,
                        self.id(f"course/{ck}"),
                        m["kind"],
                        m["title"],
                        m.get("mime_type") or ("text/vtt" if is_transcript else None),
                        len(pages) if pages else None,
                        m.get("duration_s"),
                        self.at(m["recorded"]) if m.get("recorded") else None,
                        m.get("processing_status", default_status),
                        m.get("processing_error"),
                        platform,
                        f"{ck}-{m['key']}",
                        url,
                        content_hash({"title": m["title"], "pages": pages, "cues": cues}),
                        self.now - timedelta(days=2),
                        self.now - timedelta(minutes=12),
                    ),
                )
                self.bump("materials")
                for n, page in enumerate(pages, start=1):
                    drafts.append(
                        _ChunkDraft(
                            ref=f"{ck}/{m['key']}#{n}",
                            course_key=ck,
                            material_key=m["key"],
                            post_key=None,
                            text=f"[{code} · {m['title']} · p.{n}]\n{page}",
                            page=n,
                        )
                    )
                for n, cue in enumerate(cues, start=1):
                    drafts.append(
                        _ChunkDraft(
                            ref=f"{ck}/{m['key']}#{n}",
                            course_key=ck,
                            material_key=m["key"],
                            post_key=None,
                            text=f"[{code} · {m['title']} · {mmss(cue['start_s'])}]\n{cue['text']}",
                            start_s=cue["start_s"],
                            end_s=cue["end_s"],
                        )
                    )
        return drafts

    async def chunks(self, drafts: list[_ChunkDraft], vectors: list[list[float]]) -> None:
        for d, vec in zip(drafts, vectors, strict=True):
            mat_id = (
                self.id(f"material/{d.course_key}/{d.material_key}") if d.material_key else None
            )
            post_id = self.id(f"post/{d.post_key}") if d.post_key else None
            row = await self.exec(
                "insert into chunks (user_id, course_id, material_id, post_id, material_version, "
                "text, page, start_s, end_s, token_count, embedding) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::extensions.vector) returning id",
                (
                    self.user_id,
                    self.id(f"course/{d.course_key}"),
                    mat_id,
                    post_id,
                    1 if mat_id else None,
                    d.text,
                    d.page,
                    d.start_s,
                    d.end_s,
                    approx_tokens(d.text),
                    to_pgvector(vec),
                ),
            )
            self.chunk_ids[d.ref] = row["id"]
            self.chunk_info[row["id"]] = {"draft": d}
            self.bump("chunks")

    async def citation(self, chunk_id: int) -> dict[str, Any]:
        """Resolved citation (S02 `Citation` shape) for seeded study sets and messages."""
        row = await self.exec(
            "select c.id, c.text, c.page, c.start_s, c.end_s, co.code, "
            "coalesce(m.title, p.title) as title, coalesce(m.platform, p.platform) as platform, "
            "coalesce(m.source_url, p.source_url) as url, m.kind as mkind, p.kind as pkind, "
            "coalesce(m.last_synced_at, p.last_synced_at) as synced "
            "from chunks c join courses co on co.id = c.course_id "
            "left join materials m on m.id = c.material_id left join posts p on p.id = c.post_id "
            "where c.id = %s and c.user_id = %s",
            (chunk_id, self.user_id),
        )
        kind = CITATION_KIND.get(row["mkind"]) if row["mkind"] else row["pkind"]
        if row["start_s"] is not None:
            deep = f"{row['url']}?time={row['start_s']}"
        elif row["page"] is not None and row["mkind"] in {"file", "syllabus"}:
            deep = f"{row['url']}#page={row['page']}"
        else:
            deep = row["url"]
        quote = row["text"].split("\n", 1)[-1][:200]
        return {
            "chunk_id": row["id"],
            "title": row["title"],
            "kind": kind,
            "platform": row["platform"],
            "course_code": row["code"],
            "page": row["page"],
            "start_s": row["start_s"],
            "end_s": row["end_s"],
            "url": row["url"],
            "deep_link": deep,
            "quote": quote,
            "last_synced_at": row["synced"].isoformat(),
            "status": "current",
        }

    async def changes(self) -> None:
        for ch in self.fx.get("changes", []):
            kind, key = ch["entity"].split("/", 1)
            course = (
                self.fx["_item_course"][key] if kind == "item" else self.fx["_post_course"][key]
            )

            def value(v: Any) -> Any:
                if isinstance(v, dict) and "date" in v:
                    return self.at(v["date"]).isoformat()
                if isinstance(v, dict) and "post_body" in v:
                    return self.post_body[v["post_body"]]
                return v

            detected = self.at(ch["detected"])
            await self.exec(
                "insert into changes (id, user_id, entity_type, entity_id, course_id, field, "
                "old_value, new_value, detected_at, seen_at) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"change/{ch['key']}"),
                    self.user_id,
                    kind,
                    self.id(f"{kind}/{key}"),
                    self.id(f"course/{course}"),
                    ch["field"],
                    Jsonb(value(ch["old"])),
                    Jsonb(value(ch["new"])),
                    detected,
                    detected + timedelta(hours=1) if ch.get("seen") else None,
                ),
            )
            self.bump("changes")

    async def study(self) -> None:
        for ss in self.fx.get("study_sets", []):
            payload = json.loads(json.dumps(ss["payload"]))
            cited: dict[str, Any] = {}
            for entry in _payload_entries(payload):
                ids = [self.chunk_ids[r] for r in entry.pop("refs", [])]
                entry["chunk_ids"] = ids
                for cid in ids:
                    cited[str(cid)] = await self.citation(cid)
            payload["citations"] = cited
            await self.exec(
                "insert into study_sets (id, user_id, course_id, type, title, payload, created_at) "
                "values (%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"studyset/{ss['key']}"),
                    self.user_id,
                    self.id(f"course/{ss['course']}") if ss.get("course") else None,
                    ss["type"],
                    ss["title"],
                    Jsonb(payload),
                    self.at(ss.get("created", "now")),
                ),
            )
            self.bump("study_sets")
        for b in self.fx.get("study_blocks", []):
            start = self.at(b["start"])
            await self.exec(
                "insert into study_blocks (id, user_id, course_id, item_id, title, start_at, "
                "end_at, status, decided_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.id(f"block/{b['key']}"),
                    self.user_id,
                    self.id(f"course/{b['course']}") if b.get("course") else None,
                    self.id(f"item/{b['item']}") if b.get("item") else None,
                    b["title"],
                    start,
                    start + timedelta(minutes=b["minutes"]),
                    b["status"],
                    self.at(b["decided"]) if b.get("decided") else None,
                ),
            )
            self.bump("study_blocks")

    async def conversations(self) -> None:
        for conv in self.fx.get("conversations", []):
            updated = self.at(conv["updated"])
            conv_id = self.id(f"conversation/{conv['key']}")
            await self.exec(
                "insert into conversations (id, user_id, title, updated_at, created_at) "
                "values (%s,%s,%s,%s,%s)",
                (conv_id, self.user_id, conv["title"], updated, updated),
            )
            self.bump("conversations")
            for i, msg in enumerate(conv["messages"]):
                refs = [a for k, a in _TEMPLATE.findall(msg["text"]) if k == "cite"]
                citations = [await self.citation(self.chunk_ids[r]) for r in refs]
                content = {
                    "text": self.render(msg["text"]),
                    "citations": citations,
                    "study_set_ids": [],
                    "block_ids": [],
                }
                await self.exec(
                    "insert into messages (id, user_id, conversation_id, role, content, "
                    "created_at) values (%s,%s,%s,%s,%s,%s)",
                    (
                        self.id(f"message/{conv['key']}/{i}"),
                        self.user_id,
                        conv_id,
                        msg["role"],
                        Jsonb(content),
                        updated + timedelta(seconds=i * 5),
                    ),
                )
                self.bump("messages")


async def user_has_data(conn: AsyncConnection[Any], user_id: UUID) -> bool:
    cur = await conn.execute(
        "select exists(select 1 from courses where user_id = %s) as found", (user_id,)
    )
    row = await cur.fetchone()
    return bool(row and row["found"])


async def seed_user(
    conn: AsyncConnection[Any],
    user_id: UUID,
    embedder: EmbeddingProvider,
    *,
    reset: bool = False,
    now: datetime | None = None,
    namespace: str = DEFAULT_NAMESPACE,
    seed_dir: Path = SEED_DIR,
) -> SeedResult:
    """Load the seed semester for `user_id` in one transaction. Embeddings are computed first,
    so a provider failure writes nothing."""
    fx = load_fixtures(seed_dir)
    now = now or datetime.now(UTC)
    if await user_has_data(conn, user_id) and not reset:
        raise SeedExistsError(
            "This account already has course data. Re-run with --reset to replace it."
        )
    loader = _Loader(conn, user_id, fx, now, namespace)

    async with conn.transaction():
        if reset:
            await delete_user_data(conn, user_id)
        await loader.profile_and_connections()
        await loader.courses_and_links()
        await loader.items()
        post_drafts = await loader.posts()
        material_drafts = await loader.materials()
        drafts = material_drafts + post_drafts
        vectors = await embedder.embed([d.text for d in drafts])
        await loader.chunks(drafts, vectors)
        await loader.changes()
        await loader.study()
        await loader.conversations()
    return SeedResult(user_id=user_id, counts=loader.counts)


# ---------------------------------------------------------------------------------------------
# Auth user (the student account the seed belongs to)
# ---------------------------------------------------------------------------------------------
LOCAL_DEFAULT_PASSWORD = "demo-password-311"  # local stack only; hosted needs --password


def is_local(url: str) -> bool:
    return "127.0.0.1" in url or "localhost" in url


async def ensure_auth_user(
    conn: AsyncConnection[Any],
    email: str,
    password: str | None,
    *,
    supabase_url: str,
    service_key: str | None,
) -> UUID:
    """Return the auth user's id for `email`, creating a confirmed email/password user if needed.

    With a service key: Supabase admin API (works on the hosted project). Without: direct SQL
    into `auth.users` + `auth.identities` (local stack only), so sign-in still works locally.
    """
    cur = await conn.execute("select id from auth.users where email = %s", (email,))
    row = await cur.fetchone()
    if row:
        return row["id"]
    if password is None:
        if not is_local(supabase_url):
            raise SeedError("Creating a hosted demo account needs --password (or SEED_PASSWORD).")
        password = LOCAL_DEFAULT_PASSWORD
    if service_key:
        import httpx

        headers = {"apikey": service_key}
        if not service_key.startswith("sb_"):  # legacy JWT keys also go in Authorization
            headers["Authorization"] = f"Bearer {service_key}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{supabase_url.rstrip('/')}/auth/v1/admin/users",
                headers=headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
        if resp.status_code >= 400:
            raise SeedError(f"Supabase admin API refused to create {email}: {resp.status_code}")
        return UUID(resp.json()["id"])
    if not is_local(supabase_url):
        raise SeedError("Creating a hosted demo account needs SUPABASE_SERVICE_ROLE_KEY.")
    cur = await conn.execute(
        "insert into auth.users (instance_id, id, aud, role, email, encrypted_password, "
        "email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at, "
        "confirmation_token, recovery_token, email_change_token_new, email_change) values "
        "('00000000-0000-0000-0000-000000000000', gen_random_uuid(), 'authenticated', "
        "'authenticated', %s, extensions.crypt(%s, extensions.gen_salt('bf')), now(), "
        """'{"provider": "email", "providers": ["email"]}', '{}', now(), now(), '', '', '', '') """
        "returning id",
        (email, password),
    )
    row = await cur.fetchone()
    assert row is not None
    user_id: UUID = row["id"]
    await conn.execute(
        "insert into auth.identities (id, user_id, provider_id, identity_data, provider, "
        "last_sign_in_at, created_at, updated_at) values (gen_random_uuid(), %s, %s, "
        "jsonb_build_object('sub', %s::text, 'email', %s::text), 'email', now(), now(), now())",
        (user_id, str(user_id), str(user_id), email),
    )
    return user_id
