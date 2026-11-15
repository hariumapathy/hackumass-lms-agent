import Link from "next/link";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Platform, SourceStatus } from "@/lib/api/types";
import { isConnectable, PLATFORM_LABEL } from "@/lib/platforms";
import { shortAgo } from "@/lib/time";

/** Per-source freshness (S32 rule 4): age, Reconnect for expired sessions, Refresh when stale. */
export function FreshnessBar({
  sources,
  now,
  onSyncNow,
}: {
  sources: SourceStatus[];
  now: Date;
  onSyncNow: (platform: Platform) => void;
}) {
  return (
    <section aria-label="Sources" className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      {sources.filter((s) => isConnectable(s.platform)).map((s) => {
        const label = PLATFORM_LABEL[s.platform];
        const reconnect = s.connection_status === "needs_reconnect";
        return (
          <span
            key={s.platform}
            className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 shadow-xs"
          >
            <span
              aria-hidden
              className={`size-1.5 rounded-full ${reconnect || s.stale ? "bg-highlight" : "bg-emerald-600"}`}
            />
            {(reconnect || s.stale) && <AlertTriangle className="size-3.5 text-amber-600" aria-label="out of date" />}
            {label} · {s.running ? <Loader2 className="size-3.5 animate-spin" aria-label="updating" /> : s.last_sync_at ? `updated ${shortAgo(s.last_sync_at, now)} ago` : "not updated yet"}
            {reconnect ? (
              <Link
                href={`/onboarding?reconnect=${s.platform}`}
                aria-label={`Reconnect ${label}`}
                className="font-medium text-foreground underline"
              >
                Reconnect
              </Link>
            ) : (
              s.stale &&
              !s.running && (
                <Button variant="ghost" size="xs" onClick={() => onSyncNow(s.platform)} aria-label={`Refresh ${label}`}>
                  <RefreshCw aria-hidden /> Refresh
                </Button>
              )
            )}
          </span>
        );
      })}
    </section>
  );
}
