"""Pydantic row models (derived from the S01 schema). S01 adds the rest; S20 needs `profiles`."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

DEFAULT_TIMEZONE = "America/New_York"


class Profile(BaseModel):
    user_id: UUID
    display_name: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    model_choice: str | None = None
    created_at: datetime | None = None
