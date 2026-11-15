import { buildStudyFixtures } from "./study-fixtures";
// Mock data shaped like S03 seed data ("Fall 2026"), with dates relative to `now`
// so the mock app always looks current. Used by MSW handlers (dev mock mode + tests).
import type {
  Change,
  Citation,
  ChatEvent,
  Connection,
  ConversationSummary,
  CourseDetail,
  CourseSummary,
  Item,
  ItemType,
  Me,
  Message,
  Platform,
  Post,
  SourceStatus,
  Today,
} from "@/lib/api/types";

export const TZ = "America/New_York";

export const COURSE_IDS = {
  cs311: "6f1c1d2e-0311-4a5b-9c11-000000000311",
  cs320: "6f1c1d2e-0320-4a5b-9c11-000000000320",
  math235: "6f1c1d2e-0235-4a5b-9c11-000000000235",
  stats315: "6f1c1d2e-0315-4a5b-9c11-000000000315",
} as const;

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

const iso = (d: Date) => d.toISOString();
const at = (now: Date, ms: number) => new Date(now.getTime() + ms);

/** YYYY-MM-DD for `d` in `tz`. */
export function localDate(d: Date, tz: string = TZ): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
}

const CANVAS = "https://example.instructure.com";
const GRADESCOPE = "https://example.gradescope.com";

interface ItemSeed {
  id: string;
  course: keyof typeof COURSE_IDS;
  type: ItemType;
  title: string;
  dueInHours: number | null;
  points?: number;
  status?: Item["status"];
  changed?: string[];
  platforms: Platform[];
}

const COURSES: Omit<CourseSummary, "upcoming_count">[] = [
  { id: COURSE_IDS.cs311, code: "COMPSCI 311", name: "Introduction to Algorithms", term: "Fall 2026", color: "#7c3aed", platforms: ["canvas", "gradescope", "echo360"] },
  { id: COURSE_IDS.cs320, code: "COMPSCI 320", name: "Software Engineering", term: "Fall 2026", color: "#0891b2", platforms: ["canvas", "gradescope"] },
  { id: COURSE_IDS.math235, code: "MATH 235", name: "Introduction to Linear Algebra", term: "Fall 2026", color: "#ea580c", platforms: ["canvas"] },
  { id: COURSE_IDS.stats315, code: "STATS 315", name: "Statistics I", term: "Fall 2026", color: "#16a34a", platforms: ["canvas"] },
];

const ITEM_SEEDS: ItemSeed[] = [
  { id: "a0000000-0000-4000-8000-000000000001", course: "stats315", type: "assignment", title: "HW 6", dueInHours: -14, points: 20, platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000002", course: "cs320", type: "lab", title: "Lab 4", dueInHours: 2, points: 10, platforms: ["canvas", "gradescope"] },
  { id: "a0000000-0000-4000-8000-000000000003", course: "math235", type: "quiz", title: "Quiz 7", dueInHours: 30, points: 5, platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000004", course: "cs311", type: "assignment", title: "HW5", dueInHours: 3 * 24, points: 60, status: "changed", changed: ["points"], platforms: ["canvas", "gradescope"] },
  { id: "a0000000-0000-4000-8000-000000000005", course: "cs320", type: "project", title: "Project milestone 2", dueInHours: 5 * 24, points: 50, platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000006", course: "cs311", type: "exam", title: "Midterm 1", dueInHours: 6 * 24, points: 100, status: "changed", changed: ["due_at"], platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000007", course: "math235", type: "exam", title: "Midterm 2", dueInHours: 18 * 24, points: 100, platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000008", course: "stats315", type: "assignment", title: "HW 7", dueInHours: 10 * 24, points: 20, platforms: ["canvas"] },
  { id: "a0000000-0000-4000-8000-000000000009", course: "cs311", type: "assignment", title: "HW4", dueInHours: -6 * 24, points: 50, platforms: ["canvas", "gradescope"] },
];

function courseOf(key: keyof typeof COURSE_IDS) {
  return COURSES.find((c) => c.id === COURSE_IDS[key])!;
}

function buildItem(seed: ItemSeed, now: Date): Item {
  const course = courseOf(seed.course);
  return {
    id: seed.id,
    course_id: course.id,
    course_code: course.code,
    type: seed.type,
    title: seed.title,
    due_at: seed.dueInHours === null ? null : iso(at(now, seed.dueInHours * HOUR)),
    points: seed.points ?? null,
    status: seed.status ?? "active",
    changed_fields: seed.changed ?? [],
    sources: seed.platforms.map((p) => ({
      platform: p,
      source_url:
        p === "gradescope"
          ? `${GRADESCOPE}/courses/90${seed.id.slice(-3)}/assignments/77${seed.id.slice(-3)}`
          : `${CANVAS}/courses/12${seed.id.slice(-3)}/assignments/99${seed.id.slice(-3)}`,
      last_synced_at: iso(at(now, -12 * 60_000)),
    })),
  };
}

export function buildFixtures(now: Date = new Date()) {
  const items = ITEM_SEEDS.map((s) => buildItem(s, now));
  const courses: CourseSummary[] = COURSES.map((c) => ({
    ...c,
    upcoming_count: items.filter((i) => i.course_id === c.id && i.due_at && new Date(i.due_at) > now).length,
  }));

  const connections: Connection[] = [
    { platform: "canvas", status: "active", expires_at: iso(at(now, 60 * DAY)), last_sync_at: iso(at(now, -12 * 60_000)), account_label: "Demo Student" },
    { platform: "gradescope", status: "active", last_sync_at: iso(at(now, -40 * 60_000)) },
    { platform: "piazza", status: "needs_reconnect", last_sync_at: iso(at(now, -3 * DAY)), last_error: "Session expired" },
  ];

  const sources: SourceStatus[] = [
    { platform: "canvas", connection_status: "active", last_sync_at: connections[0].last_sync_at, running: false, stale: false },
    { platform: "gradescope", connection_status: "active", last_sync_at: connections[1].last_sync_at, running: false, stale: false },
    { platform: "piazza", connection_status: "needs_reconnect", last_sync_at: connections[2].last_sync_at, running: false, stale: true },
  ];

  const me: Me = {
    user_id: "u0000000-0000-4000-8000-000000000001",
    display_name: "Demo Student",
    timezone: TZ,
    model_choice: "openai/gpt-default",
    connections,
  };

  const midterm = items.find((i) => i.title === "Midterm 1")!;
  const hw5 = items.find((i) => i.title === "HW5")!;
  const changes: Change[] = [
    {
      id: "c0000000-0000-4000-8000-000000000001",
      entity_type: "item",
      entity_id: midterm.id,
      course_code: "COMPSCI 311",
      field: "due_at",
      old_value: iso(at(now, 4 * DAY)),
      new_value: midterm.due_at,
      detected_at: iso(at(now, -5 * HOUR)),
      seen: false,
      summary: "COMPSCI 311 Midterm 1 moved 2 days later",
    },
    {
      id: "c0000000-0000-4000-8000-000000000002",
      entity_type: "item",
      entity_id: hw5.id,
      course_code: "COMPSCI 311",
      field: "points",
      old_value: 50,
      new_value: 60,
      detected_at: iso(at(now, -26 * HOUR)),
      seen: false,
      summary: "COMPSCI 311 HW5 points 50 → 60",
    },
  ];

  const posts: Post[] = [
    {
      id: "p0000000-0000-4000-8000-000000000001",
      course_id: COURSE_IDS.math235,
      kind: "announcement",
      title: "Office hours moved",
      excerpt: "This week's Thursday office hours move to Friday 2–3 PM in LGRT 1234.",
      posted_at: iso(at(now, -2 * HOUR)),
      source_url: `${CANVAS}/courses/12235/discussion_topics/5501`,
      status: "active",
    },
    {
      id: "p0000000-0000-4000-8000-000000000002",
      course_id: COURSE_IDS.cs311,
      kind: "piazza",
      title: "Midterm coverage",
      excerpt: "Midterm 1 covers everything through dynamic programming, not graphs.",
      posted_at: iso(at(now, -20 * HOUR)),
      source_url: "https://example.piazza.com/class/abc123/post/412",
      status: "changed",
    },
  ];

  const today = buildToday(now, items, changes, posts, sources);

  const citations: Citation[] = [
    {
      chunk_id: 8812,
      title: "Lecture 7 slides",
      kind: "slides",
      platform: "canvas",
      course_code: "COMPSCI 311",
      page: 12,
      url: `${CANVAS}/courses/12311/files/44012`,
      deep_link: `${CANVAS}/courses/12311/files/44012`,
      quote: "Memoization stores solutions to subproblems so each is solved only once.",
      last_synced_at: iso(at(now, -12 * 60_000)),
      status: "current",
    },
    {
      chunk_id: 9930,
      title: "Lecture Nov 11",
      kind: "transcript",
      platform: "echo360",
      course_code: "COMPSCI 311",
      start_s: 1421,
      end_s: 1481,
      url: "https://example.echo360.org/lesson/abc/classroom",
      deep_link: "https://example.echo360.org/lesson/abc/classroom#t=1421",
      quote: "so when we memoize, we're trading memory for time",
      last_synced_at: iso(at(now, -3 * DAY)),
      status: "changed",
    },
    {
      chunk_id: 4410,
      title: "Midterm coverage",
      kind: "post",
      platform: "piazza",
      course_code: "COMPSCI 311",
      url: "https://example.piazza.com/class/abc123/post/412",
      deep_link: "https://example.piazza.com/class/abc123/post/412",
      quote: "Midterm 1 covers everything through dynamic programming, not graphs.",
      last_synced_at: iso(at(now, -20 * HOUR)),
      status: "removed",
    },
  ];

  const conversations: ConversationSummary[] = [
    { id: "d0000000-0000-4000-8000-000000000001", title: "What's on the CS 311 midterm?", updated_at: iso(at(now, -DAY)), study_sets: [] },
  ];

  const conversationMessages: Record<string, Message[]> = {
    [conversations[0].id]: [
      {
        id: "m0000000-0000-4000-8000-000000000001",
        role: "user",
        text: "What's on the CS 311 midterm?",
        citations: [],
        study_set_ids: [],
        block_ids: [],
        created_at: iso(at(now, -DAY)),
      },
      {
        id: "m0000000-0000-4000-8000-000000000002",
        role: "assistant",
        text: "Midterm 1 covers everything through **dynamic programming**, not graphs [cite:chunk_4410]. Review memoization [cite:chunk_8812].",
        citations: [citations[2], citations[0]],
        study_set_ids: ["e0000000-0000-4000-8000-000000000001", "e0000000-0000-4000-8000-000000000002"],
        block_ids: [],
        created_at: iso(at(now, -DAY + 30_000)),
      },
    ],
  };

  const courseDetails: Record<string, CourseDetail> = Object.fromEntries(
    courses.map((c) => [
      c.id,
      {
        ...c,
        items: items.filter((i) => i.course_id === c.id),
        recent_posts: posts.filter((p) => p.course_id === c.id),
        materials:
          c.id === COURSE_IDS.cs311
            ? [
                { id: "f0000000-0000-4000-8000-000000000001", title: "Lecture 7 slides", kind: "file", processing_status: "done", source_url: `${CANVAS}/courses/12311/files/44012` },
                { id: "f0000000-0000-4000-8000-000000000002", title: "Syllabus", kind: "syllabus", processing_status: "done", source_url: `${CANVAS}/courses/12311/assignments/syllabus` },
                { id: "f0000000-0000-4000-8000-000000000003", title: "Lecture Nov 11", kind: "transcript", processing_status: "skipped", source_url: "https://example.echo360.org/lesson/abc/classroom" },
              ]
            : [
                {
                  id: `f1000000-0000-4000-8000-000000000${c.code.slice(-3)}`,
                  title: "Syllabus",
                  kind: "syllabus",
                  processing_status: "done",
                  source_url: `${CANVAS}/courses/12${c.code.slice(-3)}/assignments/syllabus`,
                },
              ],
        syllabus_excerpt: `${c.name}: lectures, weekly homework, two midterms and a final.`,
      } satisfies CourseDetail,
    ]),
  );

  return { ...buildStudyFixtures(now), now, me, items, courses, courseDetails, changes, posts, sources, today, citations, conversations, conversationMessages };
}

export type Fixtures = ReturnType<typeof buildFixtures>;

/** Buckets items like S32's backend rules (approximation for mocks only). */
export function buildToday(now: Date, items: Item[], changes: Change[], posts: Post[], sources: SourceStatus[]): Today {
  const todayStr = localDate(now);
  const active = items.filter((i) => i.status !== "removed" && i.due_at);
  const due = (i: Item) => new Date(i.due_at!);
  const byDue = (a: Item, b: Item) => due(a).getTime() - due(b).getTime();
  return {
    date: todayStr,
    timezone: TZ,
    overdue: active.filter((i) => due(i) < now && due(i).getTime() > now.getTime() - 7 * DAY).sort(byDue),
    due_today: active.filter((i) => due(i) >= now && localDate(due(i)) === todayStr).sort(byDue),
    due_this_week: active
      .filter((i) => localDate(due(i)) > todayStr && due(i).getTime() <= now.getTime() + 7 * DAY && i.type !== "exam")
      .sort(byDue),
    upcoming_exams: active.filter((i) => i.type === "exam" && due(i) >= now && due(i).getTime() <= now.getTime() + 30 * DAY).sort(byDue),
    changes: changes.filter((c) => !c.seen),
    new_posts: posts.filter((p) => new Date(p.posted_at).getTime() >= now.getTime() - 72 * HOUR),
    sources,
  };
}

/** Scripted chat stream (S02 event order). Text deltas deliberately split a citation marker. */
export function scriptedChat(conversationId: string, f: Fixtures): ChatEvent[] {
  return [
    { type: "run_started", data: { run_id: "r-1", conversation_id: conversationId, user_message_id: "um-1" } },
    { type: "status", data: { id: "t1", label: "Checking your COMPSCI 311 exams…", state: "started", tool: "get_items" } },
    { type: "status", data: { id: "t1", label: "Checking your COMPSCI 311 exams…", state: "done", tool: "get_items" } },
    { type: "status", data: { id: "t2", label: "Searching lecture slides and Piazza…", state: "started", tool: "search_materials" } },
    { type: "status", data: { id: "t2", label: "Searching lecture slides and Piazza…", state: "done", tool: "search_materials" } },
    { type: "text", data: { delta: "**Midterm 1** is in 6 days. It covers everything through dynamic programming, not graphs [cite:chu" } },
    { type: "text", data: { delta: "nk_4410].\n\n- Review memoization [cite:chunk_8812]\n- Rewatch the Nov 11 lecture [cite:chunk_9930]" } },
    { type: "text", data: { delta: " [cite:chunk_77]" } },
    { type: "citations", data: { citations: [f.citations[2], f.citations[0], f.citations[1]], dropped: [77] } },
    {
      type: "done",
      data: {
        run_id: "r-1",
        message_id: "am-1",
        final_text:
          "**Midterm 1** is in 6 days. It covers everything through dynamic programming, not graphs [cite:chunk_4410].\n\n- Review memoization [cite:chunk_8812]\n- Rewatch the Nov 11 lecture [cite:chunk_9930]",
      },
    },
  ];
}

/** Study-mode variant keeps S02 ordering: cards after text, before citations. */
export function scriptedStudyChat(conversationId: string, f: Fixtures): ChatEvent[] {
  const events = scriptedChat(conversationId, f);
  const additions: ChatEvent[] = [
    ...f.studySets.map((study_set): ChatEvent => ({ type: "study_set", data: { study_set } })),
    { type: "approval_required", data: { blocks: f.studyBlocks, summary: "Add 5 study sessions to your calendar?" } },
  ];
  events.splice(events.findIndex((e) => e.type === "citations"), 0, ...additions);
  return events;
}
