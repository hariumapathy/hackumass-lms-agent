import Link from "next/link";
import type { StudySet, StudySetSummary } from "@/lib/api/types";

export const STUDY_LABELS = { plan: "Study plan", quiz: "Practice quiz", flashcards: "Flashcards" };
export function StudySetCard({ set }: { set: StudySet | StudySetSummary }) {
  const payload = "payload" in set ? set.payload : {};
  const items = payload[set.type === "plan" ? "days" : set.type === "quiz" ? "questions" : "cards"];
  const count = Array.isArray(items) ? items.length : null;
  const units = set.type === "plan" ? " days" : set.type === "quiz" ? " Qs" : "";
  return (
    <Link href={`/study/${encodeURIComponent(set.id)}`} className="block rounded-xl border bg-card p-4 hover:bg-accent focus-visible:outline-2">
      <span className="block text-sm font-medium">{STUDY_LABELS[set.type]}{count !== null && ` · ${count}${units}`}</span>
      <span className="block text-sm text-muted-foreground">{set.title}</span>
    </Link>
  );
}
