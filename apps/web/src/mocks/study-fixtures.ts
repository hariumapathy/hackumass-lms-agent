import type { StudySet, StudyBlock } from "@/lib/api/types";

export function buildStudyFixtures(now: Date) {
  const created_at = now.toISOString();
  const course_id = "6f1c1d2e-0311-4a5b-9c11-000000000311";
  const days = Array.from({ length: 5 }, (_, i) => ({
    date: new Date(now.getTime() + (i + 1) * 86400000).toISOString().slice(0, 10), minutes: 45,
    topics: ["Dynamic programming"], tasks: [{ text: `Day ${i + 1}: Practice memoization and trace a recurrence`, chunk_ids: [8812] }],
  }));
  const studySets: StudySet[] = [
    { id: "e0000000-0000-4000-8000-000000000001", type: "plan", title: "CS 311 midterm study plan", course_id, created_at, payload: { days } },
    { id: "e0000000-0000-4000-8000-000000000002", type: "quiz", title: "CS 311 dynamic programming quiz", course_id, created_at, payload: { questions: [
      { type: "mcq", prompt: "What does memoization store?", choices: ["Solutions to subproblems", "Only final answers", "Every possible input", "Sorted edges"], answer_index: 0, explanation: "Caching each subproblem avoids repeated work.", chunk_ids: [8812] },
      { type: "mcq", prompt: "What does memoization trade for time?", choices: ["Accuracy", "Memory", "Input size", "Correctness"], answer_index: 1, explanation: "Stored results use memory to save computation.", chunk_ids: [9930] },
      { type: "short", prompt: "Explain why overlapping subproblems help dynamic programming.", answer_text: "Reuse a stored solution instead of solving the same subproblem again.", explanation: "Repeated subproblems make caching useful.", chunk_ids: [8812] },
    ] } },
    { id: "e0000000-0000-4000-8000-000000000003", type: "flashcards", title: "CS 311 quick review", course_id, created_at, payload: { cards: [
      { front: "What is memoization?", back: "Caching solutions to subproblems.", chunk_ids: [8812] },
      { front: "What resource does caching use?", back: "Memory.", chunk_ids: [9930] },
      { front: "What does caching save?", back: "Time spent repeating computation.", chunk_ids: [8812] },
      { front: "When can a cached result be reused?", back: "When the same subproblem occurs again.", chunk_ids: [8812] },
      { front: "What is a subproblem?", back: "A smaller problem whose solution helps solve the original problem.", chunk_ids: [8812] },
    ] } },
  ];
  const studyBlocks: StudyBlock[] = days.map((day, i) => ({
    id: `b0000000-0000-4000-8000-00000000000${i + 1}`, title: `CS 311 review: day ${i + 1}`,
    start_at: `${day.date}T21:00:00Z`, end_at: `${day.date}T21:45:00Z`, course_id, status: "proposed",
  }));
  return { studySets, studyBlocks };
}
