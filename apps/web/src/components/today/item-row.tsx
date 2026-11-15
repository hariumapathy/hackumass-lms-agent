import Link from "next/link";
import {
  Circle,
  FileText,
  FlaskConical,
  FolderKanban,
  GraduationCap,
  ListChecks,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { CourseSummary, Item, ItemType, Platform, RecordStatus } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { formatDateTime, relative } from "@/lib/time";

const TYPE_ICON: Record<ItemType, LucideIcon> = {
  assignment: FileText,
  exam: GraduationCap,
  quiz: ListChecks,
  lab: FlaskConical,
  project: FolderKanban,
  other: Circle,
};

export function SourceChip({ platform, url }: { platform: Platform; url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="rounded-full border bg-background px-2.5 py-0.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-accent-foreground"
    >
      {PLATFORM_LABEL[platform]}
    </a>
  );
}

export function StatusBadge({ status }: { status: RecordStatus }) {
  if (status === "changed")
    return (
      <Badge variant="outline" className="border-highlight bg-highlight/20 text-[10px] font-semibold tracking-wide text-foreground">
        CHANGED
      </Badge>
    );
  if (status === "removed") return <Badge variant="destructive">REMOVED</Badge>;
  return null;
}

export function CourseChip({ course, fallbackCode }: { course?: CourseSummary; fallbackCode: string }) {
  const content = (
    <>
      <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: course?.color ?? "currentColor" }} aria-hidden />
      {course?.code ?? fallbackCode}
    </>
  );
  return course ? (
    <Link href={`/courses/${course.id}`} className="inline-flex items-center gap-1.5 text-xs font-medium hover:underline">
      {content}
    </Link>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">{content}</span>
  );
}

/** One deadline: course chip, title, local due time + relative, type, status, source links (S32 rule 2). */
export function ItemRow({ item, course, tz, now }: { item: Item; course?: CourseSummary; tz: string; now: Date }) {
  const Icon = TYPE_ICON[item.type];
  const dueMs = item.due_at ? new Date(item.due_at).getTime() - now.getTime() : null;
  const soon = dueMs !== null && dueMs >= 0 && dueMs < 24 * 3600_000;
  const late = dueMs !== null && dueMs < 0;
  return (
    <li className="relative flex flex-col gap-2 overflow-hidden rounded-xl border bg-card py-3 pr-3 pl-4 shadow-xs transition-shadow hover:shadow-md sm:flex-row sm:items-center sm:gap-3">
      <span aria-hidden className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: course?.color ?? "var(--primary)" }} />
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-accent text-primary">
          <Icon className="size-4" aria-label={item.type} />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <CourseChip course={course} fallbackCode={item.course_code} />
            <span className={item.status === "removed" ? "font-medium line-through" : "font-medium"}>{item.title}</span>
            <StatusBadge status={item.status} />
          </div>
          <span className="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground">
            {item.due_at ? (
              <>
                <time dateTime={item.due_at}>{formatDateTime(item.due_at, tz)}</time> ·{" "}
                <span
                  className={
                    soon
                      ? "rounded bg-highlight px-1.5 font-semibold text-highlight-foreground"
                      : late
                        ? "font-medium text-destructive"
                        : undefined
                  }
                >
                  {relative(item.due_at, now)}
                </span>
              </>
            ) : (
              "No due date"
            )}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 pl-11 sm:pl-0">
        {item.sources.map((s) => (
          <SourceChip key={`${s.platform}-${s.source_url}`} platform={s.platform} url={s.source_url} />
        ))}
      </div>
    </li>
  );
}
