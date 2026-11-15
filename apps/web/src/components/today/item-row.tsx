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
      className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
    >
      {PLATFORM_LABEL[platform]}
    </a>
  );
}

export function StatusBadge({ status }: { status: RecordStatus }) {
  if (status === "changed")
    return (
      <Badge variant="outline" className="border-amber-500/60 text-amber-700 dark:text-amber-400">
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
  return (
    <li className="flex flex-col gap-1.5 rounded-lg border px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3">
      <div className="flex min-w-0 flex-1 items-start gap-2.5">
        <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label={item.type} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <CourseChip course={course} fallbackCode={item.course_code} />
            <span className={item.status === "removed" ? "font-medium line-through" : "font-medium"}>{item.title}</span>
            <StatusBadge status={item.status} />
          </div>
          <span className="text-sm text-muted-foreground">
            {item.due_at ? (
              <>
                <time dateTime={item.due_at}>{formatDateTime(item.due_at, tz)}</time> · {relative(item.due_at, now)}
              </>
            ) : (
              "No due date"
            )}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 pl-6 sm:pl-0">
        {item.sources.map((s) => (
          <SourceChip key={`${s.platform}-${s.source_url}`} platform={s.platform} url={s.source_url} />
        ))}
      </div>
    </li>
  );
}
