import Link from "next/link";
import { useId, type ReactNode } from "react";
import { AlertTriangle, MessageSquare } from "lucide-react";
import { Empty } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import type { Change, CourseSummary, Item, Platform, Post, Today } from "@/lib/api/types";
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
  const tz = today.timezone;
  const nothingDue =
    today.overdue.length + today.due_today.length + today.due_this_week.length + today.upcoming_exams.length === 0;

  const items = (list: Item[]) => (
    <ul className="flex flex-col gap-2">
      {list.map((i) => (
        <ItemRow key={i.id} item={i} course={byId.get(i.course_id)} tz={tz} now={now} />
      ))}
    </ul>
  );

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Today <span className="font-normal text-muted-foreground">· {formatLocalDay(today.date)}</span>
        </h1>
        <FreshnessBar sources={today.sources} now={now} onSyncNow={onSyncNow} />
      </header>

      {today.changes.length > 0 && <ChangeBanner changes={today.changes} onMarkSeen={onMarkSeen} busy={markingSeen} />}

      {nothingDue && <Empty title="Nothing due this week 🎉" description="New deadlines show up here as soon as they sync." />}
      {today.overdue.length > 0 && <Section title="Overdue" count={today.overdue.length}>{items(today.overdue)}</Section>}
      {today.due_today.length > 0 && <Section title="Due today" count={today.due_today.length}>{items(today.due_today)}</Section>}
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

      <Button asChild variant="outline" className="self-start">
        <Link href={`/chat?prefill=${encodeURIComponent("What should I focus on this week?")}`}>
          <MessageSquare aria-hidden /> Ask about your week
        </Link>
      </Button>

      {courses.length > 0 && (
        <Section title="Your courses">
          <ul className="grid gap-2 sm:grid-cols-2">
            {courses.map((c) => (
              <li key={c.id} className="flex items-center justify-between rounded-lg border px-3 py-2">
                <CourseChip course={c} fallbackCode={c.code} />
                <span className="text-xs text-muted-foreground">{c.upcoming_count} upcoming</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2">
      <h2 id={id} className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
        {count !== undefined && ` (${count})`}
      </h2>
      {children}
    </section>
  );
}

function ChangeBanner({ changes, onMarkSeen, busy }: { changes: Change[]; onMarkSeen: (ids: string[]) => void; busy?: boolean }) {
  return (
    <section
      aria-label="Changes"
      className="flex flex-col gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 sm:flex-row sm:items-start"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
      <div className="flex-1">
        <p className="text-sm font-medium">
          {changes.length} {changes.length === 1 ? "change" : "changes"}
        </p>
        <ul className="text-sm">
          {changes.map((c) => (
            <li key={c.id}>{c.summary}</li>
          ))}
        </ul>
      </div>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => onMarkSeen(changes.map((c) => c.id))}>
        Mark seen
      </Button>
    </section>
  );
}

function PostRow({ post, course, now }: { post: Post; course?: CourseSummary; now: Date }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border px-3 py-2.5">
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
