"""Diff rules (S10 rule 4): meaningful fields, content hash, and change detection.

Pure functions: no DB, no clock. The pipeline (`pipeline.py`) uses them to decide
new / changed / unchanged per record.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from app.connectors.base import NCourse, NItem, NMaterial, NormalizedRecord, NPost
from app.core.hashing import content_hash

Outcome = Literal["new", "changed", "unchanged"]

# Fields that produce a `changes` row when they change (S10 rule 4).
CHANGE_FIELDS = ("title", "due_at", "points", "body", "description")


def meaningful_fields(rec: NormalizedRecord) -> dict[str, Any]:
    """What the content hash covers. Never sync timestamps."""
    if isinstance(rec, NCourse):
        return {"name": rec.name, "code": rec.code, "term": rec.term}
    if isinstance(rec, NItem):
        return {
            "type": rec.type,
            "title": rec.title,
            "description": rec.description,
            "due_at": rec.due_at,
            "points": rec.points,
        }
    if isinstance(rec, NMaterial):
        return {
            "kind": rec.kind,
            "title": rec.title,
            "mime_type": rec.mime_type,
            "text": rec.text,
            "cues": [c.model_dump() for c in rec.cues or []],
            "source_updated_at": rec.source_updated_at,  # file changed on the platform
        }
    if isinstance(rec, NPost):
        return {"kind": rec.kind, "title": rec.title, "body": rec.body, "author": rec.author}
    raise TypeError(f"unknown record {type(rec).__name__}")


def record_hash(rec: NormalizedRecord) -> str:
    return content_hash(meaningful_fields(rec))


def classify(existing_hash: str | None, new_hash: str) -> Outcome:
    if existing_hash is None:
        return "new"
    return "unchanged" if existing_hash == new_hash else "changed"


def _norm(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dataclass
class FieldChange:
    field: str
    old: Any
    new: Any


def changed_fields(old: dict[str, Any], new: dict[str, Any]) -> list[FieldChange]:
    """One entry per meaningful field whose value differs (JSON-ready values)."""
    out = []
    for f in CHANGE_FIELDS:
        if f not in new:
            continue
        o, n = _norm(old.get(f)), _norm(new.get(f))
        if o != n:
            out.append(FieldChange(f, o, n))
    return out
