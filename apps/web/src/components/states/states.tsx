"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import type { SourceStatus } from "@/lib/api/types";
import { isConnectable, PLATFORM_LABEL } from "@/lib/platforms";

export function Loading({ label = "Loading…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 py-4">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function Empty({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-12 text-center">
      <Inbox className="size-8 text-muted-foreground" aria-hidden />
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex flex-col items-center gap-3 rounded-lg border border-destructive/40 px-6 py-10 text-center">
      <AlertTriangle className="size-6 text-destructive" aria-hidden />
      <p className="text-sm">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw aria-hidden /> Try again
        </Button>
      )}
    </div>
  );
}

/** Banner for sources that are stale or need a reconnect (shown above content that may be out of date). */
export function StaleBanner({ sources }: { sources: SourceStatus[] }) {
  const bad = sources.filter((s) => isConnectable(s.platform) && (s.stale || s.connection_status === "needs_reconnect"));
  if (bad.length === 0) return null;
  return (
    <div role="status" className="flex flex-wrap items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm">
      <AlertTriangle className="size-4 text-amber-600" aria-hidden />
      {bad.map((s) => (
        <span key={s.platform}>
          {PLATFORM_LABEL[s.platform]} may be out of date
          {s.connection_status === "needs_reconnect" && (
            <>
              {" · "}
              <Link className="underline" href={`/onboarding?reconnect=${s.platform}`}>
                Reconnect
              </Link>
            </>
          )}
        </span>
      ))}
    </div>
  );
}
