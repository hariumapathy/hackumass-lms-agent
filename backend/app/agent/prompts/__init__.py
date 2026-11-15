"""System prompt (S22). Template in `system.md`; filled per request by `build_instructions`."""

from dataclasses import dataclass, field
from pathlib import Path

from app.agent.tools.courses import CourseRef

TEMPLATE = (Path(__file__).parent / "system.md").read_text(encoding="utf-8")


@dataclass
class PromptContext:
    today_local: str
    timezone: str
    courses: list[CourseRef] = field(default_factory=list)
    freshness: dict[str, str] = field(default_factory=dict)  # platform -> "12 minutes ago"
    needs_reconnect: list[str] = field(default_factory=list)


def build_instructions(ctx: PromptContext) -> str:
    course_list = (
        "\n".join(f"- {c.code}: {c.name} (id {c.id})" for c in ctx.courses) or "- none yet"
    )
    lines = []
    for platform, ago in ctx.freshness.items():
        extra = " (needs the student to reconnect)" if platform in ctx.needs_reconnect else ""
        lines.append(f"- {platform}: updated {ago}{extra}")
    return TEMPLATE.format(
        today_local=ctx.today_local,
        timezone=ctx.timezone,
        course_list=course_list,
        freshness_lines="\n".join(lines) or "- no sources connected",
    )
