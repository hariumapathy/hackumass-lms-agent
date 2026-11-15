// Frontend API types.
// REST types come from the generated OpenAPI schema (`make types` -> schema.d.ts, S02); never edit them here.
// SSE event types mirror backend/app/api/CONTRACT.md (OpenAPI can't describe SSE).
import type { components } from "./schema";

type S = components["schemas"];

export type Me = S["Me"];
export type Connection = S["Connection"];
export type SourceStatus = S["SourceStatus"];
export type SourceRef = S["SourceRef"];
export type Item = S["Item"];
export type Post = S["Post"];
export type Change = S["Change"];
export type Today = S["Today"];
export type CourseSummary = S["CourseSummary"];
export type CourseDetail = S["CourseDetail"];
export type MaterialSummary = S["MaterialSummary"];
export type Citation = S["Citation"];
export type Message = S["Message"];
export type ConversationSummary = S["ConversationSummary"];
export type ConversationDetail = S["ConversationDetail"];
export type StudySetSummary = S["StudySetSummary"];
export type StudySet = S["StudySet"];
export type StudyBlock = S["StudyBlock"];
export type ChatRequest = S["ChatRequest"];
export type SyncRequest = S["SyncRequest"];
export type SyncStartResponse = S["SyncStartResponse"];
export type SyncStatusResponse = S["SyncStatusResponse"];

export type Platform = Connection["platform"];
export type ConnectionStatus = Connection["status"];
export type RecordStatus = Item["status"];
export type ItemType = Item["type"];
export type MaterialKind = MaterialSummary["kind"];
export type ProcessingStatus = MaterialSummary["processing_status"];
export type CitationStatus = Citation["status"];

/** S02 error envelope (`backend/app/core/errors.py`). */
export interface ErrorEnvelope {
  error: { code: string; message: string; retryable: boolean; details?: unknown };
}

// ---- SSE events for POST /chat (CONTRACT.md "Events") ----
export type ChatEvent =
  | { type: "run_started"; data: { run_id: string; conversation_id: string; user_message_id: string } }
  | { type: "status"; data: { id: string; label: string; state: "started" | "done" | "failed"; tool: string } }
  | { type: "text"; data: { delta: string } }
  | { type: "study_set"; data: { study_set: StudySet } }
  | { type: "approval_required"; data: { blocks: StudyBlock[]; summary: string } }
  | { type: "citations"; data: { citations: Citation[]; dropped: number[] } }
  | { type: "done"; data: { run_id: string; message_id: string; final_text: string } }
  | { type: "error"; data: { code: string; message: string; retryable: boolean } };

export type ChatEventType = ChatEvent["type"];
