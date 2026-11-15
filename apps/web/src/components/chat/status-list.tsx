import { AlertTriangle, Check, Loader2 } from "lucide-react";
import type { StatusItem } from "./chat-state";

/** Tool progress checklist (S33 rule 2). */
export function StatusList({ items }: { items: StatusItem[] }) {
  if (items.length === 0) return null;
  return (
    <ul aria-live="polite" className="flex flex-col gap-1 text-sm text-muted-foreground">
      {items.map((s) => (
        <li key={s.id} className="flex items-center gap-2">
          {s.state === "started" && <Loader2 className="size-3.5 animate-spin" aria-label="running" />}
          {s.state === "done" && <Check className="size-3.5 text-green-600" aria-label="done" />}
          {s.state === "failed" && <AlertTriangle className="size-3.5 text-amber-600" aria-label="failed" />}
          <span>{s.label}</span>
        </li>
      ))}
    </ul>
  );
}
