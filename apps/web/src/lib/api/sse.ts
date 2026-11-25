// SSE client for POST /chat (S02, S30 rule 4). EventSource can't POST or send headers,
// so we read the fetch body stream and parse frames ourselves.
import { authHeaders, getApiConfig, toApiError } from "./client";
import { sessionRequest } from "./session-boundary";
import type { ChatEvent, ChatEventType, ChatRequest } from "./types";

export interface SseFrame {
  event: string;
  data: string;
}

/** Incremental parser: push text chunks in any split, get complete frames out. */
export class SseParser {
  private buffer = "";
  private event = "";
  private data: string[] = [];

  push(chunk: string): SseFrame[] {
    this.buffer += chunk;
    const frames: SseFrame[] = [];
    for (;;) {
      const nl = this.buffer.search(/[\r\n]/);
      if (nl === -1) break;
      const ch = this.buffer[nl];
      if (ch === "\r" && nl === this.buffer.length - 1) break; // wait: may be the first half of \r\n
      const line = this.buffer.slice(0, nl);
      this.buffer = this.buffer.slice(ch === "\r" && this.buffer[nl + 1] === "\n" ? nl + 2 : nl + 1);
      const frame = this.line(line);
      if (frame) frames.push(frame);
    }
    return frames;
  }

  /** Call at end of stream: dispatches a final event that lacked its trailing blank line. */
  flush(): SseFrame[] {
    const frames: SseFrame[] = [];
    if (this.buffer) {
      const f = this.line(this.buffer.replace(/\r$/, ""));
      this.buffer = "";
      if (f) frames.push(f);
    }
    const last = this.line("");
    if (last) frames.push(last);
    return frames;
  }

  private line(line: string): SseFrame | null {
    if (line === "") {
      if (this.data.length === 0) {
        this.event = "";
        return null;
      }
      const frame = { event: this.event || "message", data: this.data.join("\n") };
      this.event = "";
      this.data = [];
      return frame;
    }
    if (line.startsWith(":")) return null;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") this.data.push(value);
    return null;
  }
}

const KNOWN: ReadonlySet<ChatEventType> = new Set<ChatEventType>([
  "run_started",
  "status",
  "text",
  "study_set",
  "approval_required",
  "citations",
  "done",
  "error",
]);

/** Typed event, or null for unknown types / bad JSON (forward compatible, S33). */
export function toChatEvent(frame: SseFrame): ChatEvent | null {
  if (!KNOWN.has(frame.event as ChatEventType)) return null;
  try {
    return { type: frame.event, data: JSON.parse(frame.data) } as ChatEvent;
  } catch {
    return null;
  }
}

/**
 * POST /chat and dispatch events until the stream ends.
 * Errors before the stream starts (401/422/429...) throw ApiError; abort throws AbortError.
 */
export async function streamChat(
  body: ChatRequest,
  handlers: { onEvent: (e: ChatEvent) => void; signal?: AbortSignal },
): Promise<void> {
  const cfg = getApiConfig();
  const scope = sessionRequest(handlers.signal);
  try {
    const headers = await authHeaders();
    scope.assertCurrent();
    const res = await fetch(`${cfg.baseUrl.replace(/\/$/, "")}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...headers },
      body: JSON.stringify(body),
      signal: scope.signal,
    });
    scope.assertCurrent();
    if (!res.ok) {
      const err = await toApiError(res);
      scope.assertCurrent();
      if (res.status === 401) await cfg.onUnauthorized();
      throw err;
    }
    if (!res.body) return;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    const parser = new SseParser();
    const dispatch = (frames: SseFrame[]) => {
      for (const f of frames) {
        const ev = toChatEvent(f);
        scope.assertCurrent();
        if (ev) handlers.onEvent(ev);
      }
    };
    // Aborting the request doesn't always end an already-open body stream (proxies, mocks), so cancel the
    // reader too: Stop must always end the read loop.
    const signal = scope.signal;
    const onAbort = () => void reader.cancel().catch(() => {});
    signal?.addEventListener("abort", onAbort, { once: true });
    try {
      for (;;) {
        const { done, value } = await reader.read();
        scope.assertCurrent();
        if (done) break;
        dispatch(parser.push(decoder.decode(value, { stream: true })));
      }
      dispatch(parser.push(decoder.decode()));
      dispatch(parser.flush());
    } finally {
      signal?.removeEventListener("abort", onAbort);
      reader.releaseLock();
    }
  } finally {
    scope.close();
  }
}
