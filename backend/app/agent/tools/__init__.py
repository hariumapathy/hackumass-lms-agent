"""Agent tools (S21). `READ_TOOLS` is the registry the runtime (S22) hands to the Agents SDK;
S24 adds `create_study_set`, S25 adds `add_study_block`."""

from app.agent.tools import read
from app.agent.tools.args import (
    FetchLatestArgs,
    GetChangesArgs,
    GetCourseOverviewArgs,
    GetItemsArgs,
    GetMaterialArgs,
    SearchMaterialsArgs,
)
from app.agent.tools.runner import ToolSpec

READ_TOOLS: list[ToolSpec] = [
    ToolSpec(
        "get_items",
        GetItemsArgs,
        read.get_items,
        "Deadlines, exams, quizzes, labs and projects, sorted by due date. Use for any "
        "'what's due' or 'when is' question. Dates are inclusive, in the student's timezone.",
    ),
    ToolSpec(
        "get_changes",
        GetChangesArgs,
        read.get_changes,
        "Recent changes the student may have missed: moved deadlines, changed points, edited "
        "announcements.",
    ),
    ToolSpec(
        "search_materials",
        SearchMaterialsArgs,
        read.search_materials,
        "Search lecture slides, lecture recordings (transcripts), syllabi and course posts. "
        "Returns passages with chunk_id for citing.",
    ),
    ToolSpec(
        "get_material",
        GetMaterialArgs,
        read.get_material,
        "Read more of one material found by search_materials (a page range like '10-20' or a "
        "time range in seconds for recordings).",
    ),
    ToolSpec(
        "get_course_overview",
        GetCourseOverviewArgs,
        read.get_course_overview,
        "A course's syllabus highlights (grading, exam coverage, policies) and upcoming items.",
    ),
    ToolSpec(
        "fetch_latest",
        FetchLatestArgs,
        read.fetch_latest,
        "Ask for fresh data from the class sites when results look stale or incomplete, then "
        "query again. Takes up to ~15 seconds.",
    ),
]

__all__ = ["READ_TOOLS"]
