import Link from "next/link";
import { CalendarRange, Layers, ListChecks, type LucideIcon } from "lucide-react";
import type { StudySet, StudySetSummary } from "@/lib/api/types";

export const STUDY_LABELS = { plan: "Study plan", quiz: "Practice quiz", flashcards: "Flashcards" };
export const STUDY_ICONS: Record<keyof typeof STUDY_LABELS, LucideIcon> = {
  plan: CalendarRange,
  quiz: ListChecks,
  flashcards: Layers,
};

export function StudySetCard({ set }: { set: StudySet | StudySetSummary }) {
  const payload = "payload" in set ? set.payload : {};
  const items = payload[set.type === "plan" ? "days" : set.type === "quiz" ? "questions" : "cards"];
  const count = Array.isArray(items) ? items.length : null;
  const units = set.type === "plan" ? " days" : set.type === "quiz" ? " Qs" : "";
  const Icon = STUDY_ICONS[set.type];
  return (
    <Link
      href={`/study/${encodeURIComponent(set.id)}`}
      className="group flex min-w-0 items-center gap-3 rounded-xl border bg-card p-4 shadow-xs transition-all hover:border-primary/30 hover:shadow-md focus-visible:outline-2"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent text-primary" aria-hidden>
        <Icon className="size-5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="block truncate text-sm font-semibold">
          {STUDY_LABELS[set.type]}
          {count !== null && ` · ${count}${units}`}
        </span>
        <span className="block truncate text-sm text-muted-foreground">{set.title}</span>
      </span>
    </Link>
  );
}
