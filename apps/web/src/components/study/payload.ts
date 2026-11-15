// Local rendering shapes from S24 until P9 supplies generated payload types.
export interface Task { text: string; chunk_ids: number[] }
export interface Day { date: string; minutes: number; topics: string[]; tasks: Task[] }
export interface Question { type: "mcq" | "short"; prompt: string; choices?: string[]; answer_index?: number; answer_text?: string; explanation: string; chunk_ids: number[] }
export interface Card { front: string; back: string; chunk_ids: number[] }
export type Payload = { type: "plan"; days: Day[] } | { type: "quiz"; questions: Question[] } | { type: "flashcards"; cards: Card[] };
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === "string");
const ids = (v: unknown): v is number[] => Array.isArray(v) && v.every(Number.isInteger);
export function parsePayload(type: string, p: Record<string, unknown>): Payload | null {
  if (type === "plan" && Array.isArray(p.days) && p.days.length && p.days.every(d => object(d) && typeof d.date === "string" && typeof d.minutes === "number" && strings(d.topics) && Array.isArray(d.tasks) && d.tasks.every(t => object(t) && typeof t.text === "string" && ids(t.chunk_ids)))) return { type, days: p.days as Day[] };
  if (type === "quiz" && Array.isArray(p.questions) && p.questions.length && p.questions.every(q => object(q) && typeof q.prompt === "string" && typeof q.explanation === "string" && ids(q.chunk_ids) && (q.type === "short" ? typeof q.answer_text === "string" : q.type === "mcq" && strings(q.choices) && q.choices.length === 4 && Number.isInteger(q.answer_index) && Number(q.answer_index) >= 0 && Number(q.answer_index) < 4))) return { type, questions: p.questions as Question[] };
  if (type === "flashcards" && Array.isArray(p.cards) && p.cards.length && p.cards.every(c => object(c) && typeof c.front === "string" && typeof c.back === "string" && ids(c.chunk_ids))) return { type, cards: p.cards as Card[] };
  return null;
}
