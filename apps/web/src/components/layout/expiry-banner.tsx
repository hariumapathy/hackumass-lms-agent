"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api/client";

const DAY = 86_400_000;
const WARN_DAYS = 10;

/** S34 rule 1: Canvas access runs out after at most 90 days; warn across the app in the last 10 days. */
export function ExpiryBanner() {
  const [now] = useState(() => Date.now()); // captured once per mount: day-level precision is enough
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me(), staleTime: 5 * 60_000 });
  const expiresAt = me.data?.connections.find((c) => c.platform === "canvas")?.expires_at;
  if (!expiresAt) return null;

  const msLeft = new Date(expiresAt).getTime() - now;
  if (msLeft >= WARN_DAYS * DAY) return null;

  const ended = msLeft <= 0;
  const days = Math.floor(msLeft / DAY);
  const when = days === 0 ? "today" : `in ${days} ${days === 1 ? "day" : "days"}`;

  return (
    <div
      role="status"
      aria-label="Canvas connection"
      className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm"
    >
      <AlertTriangle className="size-4 text-amber-600" aria-hidden />
      <span>
        {ended
          ? "Your Canvas connection has ended, so your classes aren't updating."
          : `Your Canvas connection ends ${when}. Renewing takes about a minute.`}
      </span>
      <Link href="/onboarding?reconnect=canvas" className="font-medium underline">
        {ended ? "Reconnect Canvas" : "Renew Canvas"}
      </Link>
    </div>
  );
}
