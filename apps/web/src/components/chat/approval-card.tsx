"use client";

import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { StudyBlock } from "@/lib/api/types";
import { formatDateTime } from "@/lib/time";

export function ApprovalCard({ blocks, summary }: { blocks: StudyBlock[]; summary: string }) {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me() });
  const tz = me.data?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [result, setResult] = useState<StudyBlock[] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const locked = useRef(false);
  async function decide(approve: boolean) {
    if (locked.current) return;
    locked.current = true;
    setPending(true);
    setError(false);
    try {
      const response = await api().decideBlocks(blocks.map((b) => b.id), approve);
      if (blocks.some((b) => !response.blocks.some((r) => r.id === b.id && r.status !== "proposed"))) throw new Error("Incomplete decision");
      setResult(response.blocks);
    } catch {
      setError(true);
      locked.current = false;
    } finally {
      setPending(false);
    }
  }
  const added = result?.every((b) => b.status === "approved");
  const skipped = result?.every((b) => b.status === "declined");
  return (
    <section aria-label="Study sessions" className="space-y-3 rounded-xl border bg-card p-4">
      <h3 className="font-medium">{summary}</h3>
      <ul className="space-y-2 text-sm">{blocks.map((b) => <li key={b.id}>
        <span className="block font-medium">{b.title}</span>
        <span className="text-muted-foreground">{formatDateTime(b.start_at, tz)} – {formatDateTime(b.end_at, tz)}</span>
      </li>)}</ul>
      <div className="flex gap-2">
        <Button disabled={pending || result !== null || !blocks.length} onClick={() => void decide(true)}>Add</Button>
        <Button variant="outline" disabled={pending || result !== null || !blocks.length} onClick={() => void decide(false)}>Skip</Button>
      </div>
      <p role="status" className="text-sm">{pending ? "Saving…" : result ? added ? "Added. They'll show up in your calendar app on its next refresh." : skipped ? "Skipped." : "Your choices are saved. Some sessions were already decided." : ""}</p>
      {error && <p role="alert" className="text-sm">Couldn&apos;t save your choice. Try again.</p>}
    </section>
  );
}
