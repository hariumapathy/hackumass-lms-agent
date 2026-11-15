"""Tool argument models (S21). Flat, few optionals, enums: easy for smaller models.

`extra="forbid"` means the model can never pass `user_id` (or anything else we didn't define).
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItemType = Literal["assignment", "exam", "quiz", "lab", "project", "other"]
Platform = Literal["canvas", "gradescope", "echo360", "piazza"]
MaterialKind = Literal["slides", "transcript", "post", "syllabus", "any"]

MAX_PAGES = 20
MAX_SECONDS = 20 * 60


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _nulls_mean_default(cls, data: Any) -> Any:
        """Some models (Gemini) send `null` for every optional field; treat it as "not given"."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data


class GetItemsArgs(_Args):
    course: str | None = Field(default=None, description="Course code or name, e.g. 'CS 311'")
    type: ItemType | None = None
    from_date: date | None = None
    to_date: date | None = None
    include_past: bool = False


class GetChangesArgs(_Args):
    since_days: int = Field(default=7, ge=1, le=60)
    course: str | None = None


class SearchMaterialsArgs(_Args):
    query: str = Field(min_length=1, max_length=500)
    course: str | None = None
    kind: MaterialKind = "any"
    source: Platform | None = None
    k: int = Field(default=8, ge=1, le=12)


class GetMaterialArgs(_Args):
    material_id: str = Field(min_length=1)
    pages: str | None = Field(
        default=None, pattern=r"^\d{1,4}(-\d{1,4})?$", description="e.g. '10-20'"
    )
    start_s: int | None = Field(default=None, ge=0)
    end_s: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ranges(self) -> "GetMaterialArgs":
        if self.pages and "-" in self.pages:
            first, last = (int(p) for p in self.pages.split("-"))
            if last < first or last - first + 1 > MAX_PAGES:
                raise ValueError(f"pages must be a range of at most {MAX_PAGES} pages")
        if self.start_s is not None and self.end_s is not None:
            if self.end_s < self.start_s or self.end_s - self.start_s > MAX_SECONDS:
                raise ValueError("time range must be at most 20 minutes")
        return self


class GetCourseOverviewArgs(_Args):
    course: str = Field(min_length=1)


class FetchLatestArgs(_Args):
    course: str | None = None
    source: Platform | None = None
    what: Literal["course", "everything"] = "course"
