import Link from "next/link";
import { useId, type ReactNode } from "react";
import { AlertTriangle, MessageSquare } from "lucide-react";
import { Empty } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import type { Change, CourseSummary, Item, Platform, Post, Today } from "@/lib/api/types";
import { splitCourses } from "@/lib/courses";
import { formatLocalDay, relative } from "@/lib/time";
import { FreshnessBar } from "./freshness-bar";
import { CourseChip, ItemRow, SourceChip, StatusBadge } from "./item-row";

export interface TodayViewProps {
  today: Today;
  courses: CourseSummary[];
  now: Date;
  onMarkSeen: (ids: string[]) => void;
  markingSeen?: boolean;
  onSyncNow: (platform: Platform) => void;
}

/** The deterministic dashboard (S32). Pure: data in, UI out. */
export function TodayView({ today, courses, now, onMarkSeen, markingSeen, onSyncNow }: TodayViewProps) {
  const byId = new Map(courses.map((c) => [c.id, c]));
  const split = splitCourses(courses);
  const tz = today.timezone;
  const nothingDue =
    today.overdue.length + today.due_today.length + today.due_this_week.length + today.upcoming_exams.length === 0;

  const items = (list: Item[]) => (
    <ul className="flex flex-col gap-2.5">
      {list.map((i) => (
        <ItemRow key={i.id} item={i} course={byId.get(i.course_id)} tz={tz} now={now} />
      ))}
    </ul>
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-7">
      <header className="flex flex-col gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">{formatLocalDay(today.date)}</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Today <span className="sr-only">· {formatLocalDay(today.date)}</span>
        </h1>
        <FreshnessBar sources={today.sources} now={now} onSyncNow={onSyncNow} />
      </header>

      {today.changes.length > 0 && <ChangeBanner changes={today.changes} onMarkSeen={onMarkSeen} busy={markingSeen} />}

      {nothingDue && <Empty title="Nothing due this week 🎉" description="New deadlines show up here as soon as they sync." />}
      {today.due_today.length > 0 && (
        <Section title="Due today" count={today.due_today.length} tone="today">{items(today.due_today)}</Section>
      )}
      {today.overdue.length > 0 && (
        <Section title="Overdue" count={today.overdue.length} tone="overdue">{items(today.overdue)}</Section>
      )}
      {today.due_this_week.length > 0 && (
        <Section title="This week" count={today.due_this_week.length}>{items(today.due_this_week)}</Section>
      )}
      {today.upcoming_exams.length > 0 && (
        <Section title="Upcoming exams" count={today.upcoming_exams.length}>{items(today.upcoming_exams)}</Section>
      )}
      {today.new_posts.length > 0 && (
        <Section title="New announcements" count={today.new_posts.length}>
          <ul className="flex flex-col gap-2">
            {today.new_posts.map((p) => (
              <PostRow key={p.id} post={p} course={byId.get(p.course_id)} now={now} />
            ))}
          </ul>
        </Section>
      )}

      <div className="flex flex-col gap-3 rounded-2xl bg-maroon px-5 py-5 text-white shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          <p className="font-display text-lg font-semibold">Not sure where to start?</p>
          <p className="text-sm text-white/80">Get a plan for your week, with links to your own course materials.</p>
        </div>
        <Button asChild className="self-start bg-white text-maroon hover:bg-white/90 sm:self-auto">
          <Link href={`/chat?prefill=${encodeURIComponent("What should I focus on this week?")}`}>
            <MessageSquare aria-hidden /> Ask about your week
          </Link>
        </Button>
      </div>

      {courses.length > 0 && (
        <Section title="Your courses">
          <CourseGrid courses={split.active.length > 0 ? split.active : courses} />
          {split.active.length > 0 && split.other.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground">
                Other courses ({split.other.length})
              </summary>
              <div className="pt-2.5">
                <CourseGrid courses={split.other} />
              </div>
            </details>
          )}
        </Section>
      )}
    </div>
  );
}

function CourseGrid({ courses }: { courses: CourseSummary[] }) {
  return (
    <ul className="grid gap-2.5 sm:grid-cols-2">
      {courses.map((c) => (
        <li
          key={c.id}
          className="relative flex items-center justify-between gap-2 overflow-hidden rounded-xl border bg-card py-3 pr-3 pl-4 shadow-xs transition-shadow hover:shadow-md"
        >
          <span aria-hidden className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: c.color ?? "var(--primary)" }} />
          <CourseChip course={c} fallbackCode={c.code} />
          <span className="shrink-0 text-xs text-muted-foreground">{c.upcoming_count} upcoming</span>
        </li>
      ))}
    </ul>
  );
}

type Tone = "default" | "today" | "overdue";

const TONE_DOT: Record<Tone, string> = {
  default: "bg-muted-foreground/40",
  today: "bg-highlight",
  overdue: "bg-destructive",
};

function Section({ title, count, tone = "default", children }: { title: string; count?: number; tone?: Tone; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h2 id={id} className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <span aria-hidden className={`size-2 rounded-full ${TONE_DOT[tone]}`} />
        {title}
        {count !== undefined && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] tabular-nums tracking-normal">
            <span className="sr-only">(</span>
            {count}
            <span className="sr-only">)</span>
          </span>
        )}
      </h2>
      {children}
    </section>
  );
}

const SHOWN_CHANGES = 3;

function ChangeBanner({ changes, onMarkSeen, busy }: { changes: Change[]; onMarkSeen: (ids: string[]) => void; busy?: boolean }) {
  return (
    <section
      aria-label="Changes"
      className="flex flex-col gap-3 rounded-xl border border-highlight/60 bg-highlight/15 px-4 py-3.5 sm:flex-row sm:items-start"
    >
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-highlight text-highlight-foreground" aria-hidden>
        <AlertTriangle className="size-4" />
      </span>
      <div className="flex-1">
        <p className="text-sm font-medium">
          {changes.length} {changes.length === 1 ? "change" : "changes"}
        </p>
        <ul className="mt-1 flex flex-col gap-0.5 text-sm text-foreground/85">
          {changes.slice(0, SHOWN_CHANGES).map((c) => (
            <li key={c.id}>{c.summary}</li>
          ))}
        </ul>
        {changes.length > SHOWN_CHANGES && (
          <details className="text-sm text-foreground/85">
            <summary className="mt-1 cursor-pointer select-none font-medium text-primary">
              Show {changes.length - SHOWN_CHANGES} more
            </summary>
            <ul className="mt-0.5 flex flex-col gap-0.5">
              {changes.slice(SHOWN_CHANGES).map((c) => (
                <li key={c.id}>{c.summary}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onMarkSeen(changes.map((c) => c.id))}>
        Mark seen
      </Button>
    </section>
  );
}

function PostRow({ post, course, now }: { post: Post; course?: CourseSummary; now: Date }) {
  return (
    <li className="flex flex-col gap-1.5 rounded-xl border bg-card px-4 py-3 shadow-xs">
      <div className="flex flex-wrap items-center gap-2">
        <CourseChip course={course} fallbackCode="" />
        <span className="font-medium">{post.title}</span>
        <StatusBadge status={post.status} />
        <span className="text-xs text-muted-foreground">{relative(post.posted_at, now)}</span>
        <span className="ml-auto">
          <SourceChip platform={post.kind === "piazza" ? "piazza" : "canvas"} url={post.source_url} />
        </span>
      </div>
      <p className="line-clamp-2 text-sm text-muted-foreground">{post.excerpt}</p>
    </li>
  );
}
