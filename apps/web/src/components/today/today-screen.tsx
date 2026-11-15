"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useCourses } from "@/components/layout/app-shell";
import { ErrorState, Loading } from "@/components/states/states";
import { api } from "@/lib/api/client";
import type { Platform } from "@/lib/api/types";
import { TodayView } from "./today-view";

const FIVE_MIN = 5 * 60_000;

/** Today page: fetches /today, refreshes every 5 min and on window focus (S32 rule 7). */
export function TodayScreen() {
  const qc = useQueryClient();
  const [now, setNow] = useState(() => new Date());
  const today = useQuery({
    queryKey: ["today"],
    queryFn: async () => {
      const t = await api().today();
      setNow(new Date());
      return t;
    },
    refetchInterval: FIVE_MIN,
    refetchOnWindowFocus: true,
  });
  const courses = useCourses();

  const markSeen = useMutation({
    mutationFn: (ids: string[]) => api().markChangesSeen(ids),
    onSuccess: () => Promise.all(["today", "changes", "course"].map((key) => qc.invalidateQueries({ queryKey: [key] }))),
  });
  const syncNow = useMutation({
    mutationFn: (platform: Platform) => api().sync({ platform }),
    onSuccess: () => Promise.all(["today", "sync-status"].map((key) => qc.invalidateQueries({ queryKey: [key] }))),
  });

  if (today.isPending) return <Loading label="Loading today…" rows={5} />;
  if (today.isError) return <ErrorState error={today.error} onRetry={() => void today.refetch()} />;

  return (
    <TodayView
      today={today.data}
      courses={courses.data ?? []}
      now={now}
      onMarkSeen={(ids) => markSeen.mutate(ids)}
      markingSeen={markSeen.isPending}
      onSyncNow={(p) => syncNow.mutate(p)}
    />
  );
}
