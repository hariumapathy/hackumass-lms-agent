// One chat turn's state, built from SSE events (S02 event order, S33 rules 2–6). Pure + testable.
import type { ChatEvent, Citation, StudySet, StudyBlock } from "@/lib/api/types";

export interface StatusItem {
  id: string;
  label: string;
  state: "started" | "done" | "failed";
}

export interface TurnError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface Turn {
  studySets: StudySet[];
  approval: { blocks: StudyBlock[]; summary: string } | null;
  key: string;
  userText: string;
  status: StatusItem[];
  /** Streamed text (may contain [cite:chunk_N] markers). */
  text: string;
  /** null until the `citations` event arrives. */
  citations: Citation[] | null;
  /** Authoritative cleaned text from `done` (S33 rule 5). */
  finalText: string | null;
  error: TurnError | null;
  phase: "streaming" | "done" | "error" | "stopped";
  /** True once `done` or `error` arrived (exactly one terminal event per stream). */
  terminal: boolean;
}

export function newTurn(key: string, userText: string): Turn {
  return { key, userText, studySets: [], approval: null, status: [], text: "", citations: null, finalText: null, error: null, phase: "streaming", terminal: false };
}

export function applyEvent(turn: Turn, ev: ChatEvent): Turn {
  switch (ev.type) {
    case "status": {
      const item: StatusItem = { id: ev.data.id, label: ev.data.label, state: ev.data.state };
      const exists = turn.status.some((s) => s.id === item.id);
      return { ...turn, status: exists ? turn.status.map((s) => (s.id === item.id ? item : s)) : [...turn.status, item] };
    }
    case "text":
      return { ...turn, text: turn.text + ev.data.delta };
    case "study_set":
      return { ...turn, studySets: [...turn.studySets.filter((s) => s.id !== ev.data.study_set.id), ev.data.study_set] };
    case "approval_required":
      return { ...turn, approval: ev.data };
    case "citations":
      return { ...turn, citations: ev.data.citations };
    case "done":
      return { ...turn, finalText: ev.data.final_text, phase: "done", terminal: true };
    case "error":
      return { ...turn, error: { ...ev.data }, phase: "error", terminal: true };
    default:
      // run_started is handled by the screen.
      return turn;
  }
}

/** Status items still spinning when the run ends are shown as failed, not left spinning. */
export function settleStatus(turn: Turn): Turn {
  if (!turn.status.some((s) => s.state === "started")) return turn;
  return { ...turn, status: turn.status.map((s) => (s.state === "started" ? { ...s, state: "failed" } : s)) };
}
