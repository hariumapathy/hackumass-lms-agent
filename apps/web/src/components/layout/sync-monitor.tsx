"use client";

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

/** Refresh saved views as imports complete, including imports started in Settings/onboarding. */
export function SyncMonitor({ pollMs }: { pollMs?: number }) {
  const qc = useQueryClient();
  const previous = useRef<string | null>(null);
  const status = useQuery({
    queryKey: ["sync-status"],
    queryFn: () => api().syncStatus(),
    refetchInterval: (q) => pollMs ?? (q.state.data?.sources.some((s) => s.running) ? 3000 : 30_000),
    refetchOnWindowFocus: "always",
  });
  const snapshot = status.data ? JSON.stringify(status.data.sources) : null;

  useEffect(() => {
    if (snapshot === null) return;
    if (previous.current !== null && previous.current !== snapshot) {
      for (const key of ["today", "courses", "course", "me", "citations"]) {
        void qc.invalidateQueries({ queryKey: [key] });
      }
    }
    previous.current = snapshot;
  }, [snapshot, qc]);
  return null;
}
