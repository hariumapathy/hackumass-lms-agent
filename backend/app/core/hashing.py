"""Content fingerprints (S10 rule 4): SHA-256 of canonical JSON of the meaningful fields.

Key order never matters; callers pass only meaningful fields (never sync timestamps).
"""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def _default(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"not hashable as JSON: {type(value).__name__}")


def content_hash(fields: dict[str, Any]) -> str:
    canonical = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
