"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare } from "lucide-react";
import { Empty, ErrorState, Loading } from "@/components/states/states";
import { ItemRow, SourceChip, StatusBadge } from "@/components/today/item-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { CourseDetail, ProcessingStatus } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { relative } from "@/lib/time";

const PROCESSING_LABEL: Record<ProcessingStatus, string> = {
  pending: "Waiting",
  processing: "Processing",
  done: "Searchable",
  failed: "Failed",
  skipped: "No text",
};

/** Course page (S32 rule 6). */
export function CourseScreen({ courseId }: { courseId: string }) {
  const course = useQuery({ queryKey: ["course", courseId], queryFn: () => api().course(courseId) });
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me(), staleTime: 5 * 60_000 });

  if (course.isPending) return <Loading label="Loading course…" rows={5} />;
  if (course.isError) return <ErrorState error={course.error} onRetry={() => void course.refetch()} />;
  return <CourseView course={course.data} tz={me.data?.timezone ?? "America/New_York"} now={new Date()} />;
}

export function CourseView({ course, tz, now }: { course: CourseDetail; tz: string; now: Date }) {
  const upcoming = course.items.filter((i) => !i.due_at || new Date(i.due_at) >= now);
  const past = course.items.filter((i) => i.due_at && new Date(i.due_at) < now).reverse();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="size-3 rounded-full" style={{ backgroundColor: course.color ?? "currentColor" }} aria-hidden />
          <h1 className="text-2xl font-semibold tracking-tight">
            {course.code} <span className="font-normal text-muted-foreground">· {course.name}</span>
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {course.term}
          {course.platforms.map((p) => (
            <Badge key={p} variant="secondary">
              {PLATFORM_LABEL[p]}
            </Badge>
          ))}
        </div>
        <Button asChild variant="outline" className="self-start">
          <Link href={`/chat?prefill=${encodeURIComponent(`Help me with ${course.code}`)}`}>
            <MessageSquare aria-hidden /> Ask about this course
          </Link>
        </Button>
      </header>

      <section aria-label="Upcoming" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Upcoming ({upcoming.length})</h2>
        {upcoming.length ? (
          <ul className="flex flex-col gap-2">
            {upcoming.map((i) => (
              <ItemRow key={i.id} item={i} course={course} tz={tz} now={now} />
            ))}
          </ul>
        ) : (
          <Empty title="Nothing upcoming" />
        )}
      </section>

      {past.length > 0 && (
        <section aria-label="Past" className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Past ({past.length})</h2>
          <ul className="flex flex-col gap-2 opacity-80">
            {past.map((i) => (
              <ItemRow key={i.id} item={i} course={course} tz={tz} now={now} />
            ))}
          </ul>
        </section>
      )}

      {course.recent_posts.length > 0 && (
        <section aria-label="Recent posts" className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Recent posts</h2>
          <ul className="flex flex-col gap-2">
            {course.recent_posts.map((p) => (
              <li key={p.id} className="flex flex-col gap-1 rounded-lg border px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{p.title}</span>
                  <StatusBadge status={p.status} />
                  <span className="text-xs text-muted-foreground">{relative(p.posted_at, now)}</span>
                  <span className="ml-auto">
                    <SourceChip platform={p.kind === "piazza" ? "piazza" : "canvas"} url={p.source_url} />
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">{p.excerpt}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Materials" className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Materials</h2>
        {course.materials.length ? (
          <ul className="divide-y rounded-lg border">
            {course.materials.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                <span>
                  {m.title} <span className="text-muted-foreground">· {m.kind}</span>
                </span>
                <Badge variant={m.processing_status === "failed" ? "destructive" : "outline"}>
                  {PROCESSING_LABEL[m.processing_status]}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          <Empty title="No materials synced yet" />
        )}
      </section>
    </div>
  );
}
