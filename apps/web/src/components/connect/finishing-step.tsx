"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { ErrorState, Loading } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { SourceStatus } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";

const isLoading = (s: SourceStatus) => s.running || !s.last_sync_at;
const hasProblem = (s: SourceStatus) => s.connection_status === "needs_reconnect" || s.connection_status === "error";

/** "Go to Today" unlocks once Canvas has finished its first load (S31 step 5). */
export function canvasReady(sources: SourceStatus[] | undefined): boolean {
  const canvas = sources?.find((s) => s.platform === "canvas");
  return !!canvas && !isLoading(canvas) && !hasProblem(canvas);
}

/** S31 step 5: polls GET /sync/status until Canvas is loaded, then sends the student to Today. */
export function FinishingStep({ pollMs = 3000, onDone }: { pollMs?: number; onDone: () => void }) {
  const status = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api().syncStatus(),
    refetchInterval: (q) => (canvasReady(q.state.data?.sources) ? false : pollMs),
  });
  const ready = canvasReady(status.data?.sources);
  const courses = useQuery({
    queryKey: ["onboarding-courses"],
    queryFn: () => api().courses(),
    refetchInterval: ready ? false : pollMs,
  });

  if (status.isPending) return <Loading label="Getting your classes…" rows={2} />;
  if (status.isError) return <ErrorState error={status.error} onRetry={() => void status.refetch()} />;

  const canvas = status.data.sources.find((s) => s.platform === "canvas");
  const classCount = courses.data?.length ?? 0;

  return (
    <section aria-labelledby="finishing-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="finishing-heading" className="text-2xl font-semibold tracking-tight">
          {ready ? "You're all set" : "Getting your classes…"}
        </h1>
        <p className="text-muted-foreground">
          {ready
            ? "Your classes are ready. We'll keep them up to date for you."
            : "This usually takes a minute or two. You can leave this page open."}
        </p>
      </div>

      <ul aria-live="polite" className="flex flex-col gap-2">
        {status.data.sources.map((s) => (
          <li key={s.platform} className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3">
            <span className="font-medium">{PLATFORM_LABEL[s.platform]}</span>
            {hasProblem(s) ? (
              <span className="inline-flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
                <AlertTriangle className="size-4" aria-hidden /> Needs attention
              </span>
            ) : isLoading(s) ? (
              <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 text-sm text-green-700 dark:text-green-400">
                <CheckCircle2 className="size-4" aria-hidden /> Ready
              </span>
            )}
          </li>
        ))}
      </ul>

      {classCount > 0 && (
        <p className="font-medium">
          {classCount} {classCount === 1 ? "class" : "classes"} found
        </p>
      )}

      {canvas && hasProblem(canvas) && (
        <p role="alert" className="text-sm">
          We couldn&apos;t open your Canvas.{" "}
          <Link className="underline" href="/onboarding?reconnect=canvas">
            Link Canvas again
          </Link>
        </p>
      )}

      <Button size="lg" className="w-fit" disabled={!ready} onClick={onDone}>
        Go to Today
      </Button>
    </section>
  );
}
