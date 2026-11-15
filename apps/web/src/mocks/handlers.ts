import { studyHandlers } from "./handlers-study";
// MSW handlers for every Stage 1 endpoint in S02, backed by fixtures.ts.
// Used by the browser in mock mode (NEXT_PUBLIC_API_MOCKS=1) and by tests (msw/node).
import { http, HttpResponse } from "msw";
import type { ChatEvent, ChatRequest, ErrorEnvelope } from "@/lib/api/types";
import { buildFixtures, buildToday, scriptedChat, scriptedStudyChat, type Fixtures } from "./fixtures";

export const MOCK_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function encodeSseEvent(ev: ChatEvent): string {
  return `event: ${ev.type}\ndata: ${JSON.stringify(ev.data)}\n\n`;
}

/** Streams events as SSE, `delayMs` apart. `hang` keeps the stream open after the last event. */
export function sseResponse(events: ChatEvent[], opts: { delayMs?: number; hang?: boolean } = {}) {
  const encoder = new TextEncoder();
  const { delayMs = 0, hang = false } = opts;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let i = 0;
      const next = () => {
        if (i >= events.length) {
          if (!hang) controller.close();
          return;
        }
        controller.enqueue(encoder.encode(encodeSseEvent(events[i++])));
        timer = setTimeout(next, delayMs);
      };
      next();
    },
    cancel() {
      if (timer) clearTimeout(timer);
    },
  });
  return new HttpResponse(stream, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}

export function errorResponse(status: number, code: string, message: string, retryable = false) {
  const body: ErrorEnvelope = { error: { code, message, retryable } };
  return HttpResponse.json(body, { status });
}

export interface HandlerOptions {
  fixtures?: Fixtures;
  /** Delay between SSE events (ms). Browser mock mode uses a delay so streaming is visible. */
  chatDelayMs?: number;
}

export function createHandlers(opts: HandlerOptions = {}) {
  const f = opts.fixtures ?? buildFixtures();
  const api = (path: string) => `${MOCK_API_URL}${path}`;
  const authed = (request: Request) => (request.headers.get("Authorization") ?? "").startsWith("Bearer ");
  const unauthorized = () => errorResponse(401, "unauthorized", "Sign in again.");

  return [
    ...studyHandlers(f),
    http.get(api("/health"), () => HttpResponse.json({ status: "ok" })),

    http.get(api("/me"), ({ request }) => (authed(request) ? HttpResponse.json(f.me) : unauthorized())),

    http.get(api("/today"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      return HttpResponse.json(buildToday(f.now, f.items, f.changes, f.posts, f.sources));
    }),

    http.get(api("/courses"), ({ request }) => (authed(request) ? HttpResponse.json(f.courses) : unauthorized())),

    http.get(api("/courses/:id"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const course = f.courseDetails[String(params.id)];
      return course ? HttpResponse.json(course) : errorResponse(404, "not_found", "Course not found.");
    }),

    http.get(api("/items"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      const url = new URL(request.url);
      const courseId = url.searchParams.get("course_id");
      const type = url.searchParams.get("type");
      return HttpResponse.json(
        f.items.filter((i) => (!courseId || i.course_id === courseId) && (!type || i.type === type)),
      );
    }),

    http.get(api("/changes"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      const unseen = new URL(request.url).searchParams.get("unseen") === "true";
      return HttpResponse.json(unseen ? f.changes.filter((c) => !c.seen) : f.changes);
    }),

    http.post(api("/changes/seen"), async ({ request }) => {
      if (!authed(request)) return unauthorized();
      const { ids } = (await request.json()) as { ids: string[] };
      for (const c of f.changes) {
        if (ids.includes(c.id)) {
          c.seen = true;
          const item = f.items.find((i) => i.id === c.entity_id);
          if (item && item.status === "changed") {
            item.status = "active";
            item.changed_fields = [];
          }
        }
      }
      return new HttpResponse(null, { status: 204 });
    }),

    http.post(api("/sync"), ({ request }) =>
      authed(request) ? HttpResponse.json({ sync_run_ids: ["s0000000-0000-4000-8000-000000000001"] }) : unauthorized(),
    ),

    http.get(api("/sync/status"), ({ request }) =>
      authed(request) ? HttpResponse.json({ sources: f.sources }) : unauthorized(),
    ),

    http.get(api("/citations"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      const ids = (new URL(request.url).searchParams.get("ids") ?? "").split(",").map(Number);
      return HttpResponse.json(f.citations.filter((c) => ids.includes(c.chunk_id)));
    }),

    http.get(api("/conversations"), ({ request }) =>
      authed(request) ? HttpResponse.json(f.conversations) : unauthorized(),
    ),

    http.get(api("/conversations/:id"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const id = String(params.id);
      const conversation = f.conversations.find((c) => c.id === id);
      if (!conversation) return errorResponse(404, "not_found", "Conversation not found.");
      return HttpResponse.json({ conversation, messages: f.conversationMessages[id] ?? [] });
    }),

    http.post(api("/chat"), async ({ request }) => {
      if (!authed(request)) return unauthorized();
      const body = (await request.json()) as ChatRequest;
      const conversationId = body.conversation_id ?? "d0000000-0000-4000-8000-0000000000aa";
      if (!f.conversations.some((c) => c.id === conversationId)) {
        f.conversations.unshift({ id: conversationId, title: body.message.slice(0, 60), updated_at: new Date().toISOString() });
      }
      return sseResponse((/prep|quiz|flashcard|study/i.test(body.message) ? scriptedStudyChat : scriptedChat)(conversationId, f), { delayMs: opts.chatDelayMs ?? 0 });
    }),
  ];
}
