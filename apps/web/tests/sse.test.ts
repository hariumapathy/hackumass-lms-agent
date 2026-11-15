import { http } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ApiError, configureApi } from "@/lib/api/client";
import { SseParser, streamChat, toChatEvent } from "@/lib/api/sse";
import type { ChatEvent } from "@/lib/api/types";
import { buildFixtures, scriptedChat, scriptedStudyChat } from "@/mocks/fixtures";
import { encodeSseEvent, errorResponse, MOCK_API_URL } from "@/mocks/handlers";
import { createMockServer } from "@/mocks/server";

const fixtures = buildFixtures(new Date("2026-11-14T15:00:00Z"));
const server = createMockServer({ fixtures });
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("SSE parser and chat stream", () => {
  it("S30-T04 parses multiple events in one chunk", () => {
    const p = new SseParser();
    const frames = p.push('event: text\ndata: {"delta":"a"}\n\nevent: text\ndata: {"delta":"b"}\n\n');
    expect(frames).toEqual([
      { event: "text", data: '{"delta":"a"}' },
      { event: "text", data: '{"delta":"b"}' },
    ]);
  });

  it("S30-T04 S02-T05 reassembles one event split across chunks (incl. CRLF)", () => {
    const p = new SseParser();
    expect(p.push("event: te")).toEqual([]);
    expect(p.push('xt\r\ndata: {"del')).toEqual([]);
    expect(p.push('ta":"hi"}\r\n')).toEqual([]);
    expect(p.push("\r\n")).toEqual([{ event: "text", data: '{"delta":"hi"}' }]);
  });

  it("S30-T04 joins multi-line data and ignores comments", () => {
    const p = new SseParser();
    expect(p.push(': keep-alive\n\nevent: done\ndata: {"a":\ndata: 1}\n\n')).toEqual([
      { event: "done", data: '{"a":\n1}' },
    ]);
  });

  it("S30-T05 unknown event types are ignored without crashing", () => {
    expect(toChatEvent({ event: "mystery", data: "{}" })).toBeNull();
    expect(toChatEvent({ event: "text", data: "not json" })).toBeNull();
    expect(toChatEvent({ event: "text", data: '{"delta":"x"}' })).toEqual({ type: "text", data: { delta: "x" } });
  });

  it("S02-T06 the MSW chat mock replays the scripted stream and the client reconstructs it", async () => {
    configureApi({ getToken: async () => "tok", onUnauthorized: () => {} });
    const events: ChatEvent[] = [];
    await streamChat({ message: "Prep me for the CS 311 midterm" }, { onEvent: (e) => events.push(e) });
    expect(events).toEqual(scriptedStudyChat("d0000000-0000-4000-8000-0000000000aa", fixtures));
    expect(events[0].type).toBe("run_started");
    expect(events.at(-1)?.type).toBe("done");
  });

  it("S30-T04 a stream delivered one byte at a time still parses", async () => {
    const bytes = new TextEncoder().encode(scriptedChat("conv-1", fixtures).map(encodeSseEvent).join(""));
    server.use(
      http.post(`${MOCK_API_URL}/chat`, () => {
        let i = 0;
        const stream = new ReadableStream<Uint8Array>({
          pull(c) {
            if (i >= bytes.length) return c.close();
            c.enqueue(bytes.slice(i, i + 1));
            i += 1;
          },
        });
        return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
      }),
    );
    configureApi({ getToken: async () => "tok", onUnauthorized: () => {} });
    const types: string[] = [];
    await streamChat({ message: "hi" }, { onEvent: (e) => types.push(e.type) });
    expect(types).toEqual(scriptedChat("conv-1", fixtures).map((e) => e.type));
  });

  it("errors before the stream starts are thrown as ApiError (JSON envelope)", async () => {
    server.use(http.post(`${MOCK_API_URL}/chat`, () => errorResponse(429, "rate_limited", "Slow down.", true)));
    configureApi({ getToken: async () => "tok", onUnauthorized: () => {} });
    const err = await streamChat({ message: "hi" }, { onEvent: () => {} }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code: "rate_limited", status: 429, retryable: true });
  });
});
