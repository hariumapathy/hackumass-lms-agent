// MSW handlers for onboarding (S31) and settings (S34): connections, live login, models, profile,
// delete-my-data and the calendar feed. Spread into `createHandlers`; they mutate the shared fixtures
// so /me, /sync/status and Today reflect what the student just did.
import { http, HttpResponse } from "msw";
import type { CanvasConnectRequest, Connection, MePatch, ModelsResponse, Platform } from "@/lib/api/types";
import type { Fixtures } from "./fixtures";
import { errorResponse, MOCK_API_URL, type HandlerOptions } from "./handlers";

const DAY = 86_400_000;

export const MOCK_MODELS: ModelsResponse = {
  default: "gemini/gemini-default",
  models: [
    { id: "gemini/gemini-default", label: "Gemini", provider: "google", tier: "recommended", available: true },
    { id: "openai/gpt-default", label: "GPT", provider: "openai", tier: "recommended", available: true },
    { id: "anthropic/claude-default", label: "Claude", provider: "anthropic", tier: "recommended", available: false },
    { id: "groq/llama-3.3", label: "Llama 3.3", provider: "groq", tier: "experimental", available: true },
    { id: "ollama/llama-local", label: "Local (Ollama)", provider: "ollama", tier: "experimental", available: false },
  ],
};

export interface AccountMockOptions extends HandlerOptions {
  /** How many `pending` polls a live login returns before `succeeded`. */
  loginPendingPolls?: number;
}

export function accountHandlers(f: Fixtures, opts: AccountMockOptions = {}) {
  const api = (path: string) => `${MOCK_API_URL}${path}`;
  const authed = (request: Request) => (request.headers.get("Authorization") ?? "").startsWith("Bearer ");
  const unauthorized = () => errorResponse(401, "unauthorized", "Sign in again.");
  // Browser mock mode (non-zero chatDelayMs) also shows a few seconds of "getting your classes".
  const firstSyncMs = opts.chatDelayMs ? 4_000 : 0;
  const pendingPolls = opts.loginPendingPolls ?? 1;
  const logins = new Map<string, { platform: Platform; polls: number }>();
  let feedVersion = 0;
  const feedUrl = () => `${MOCK_API_URL}/calendar/demo-feed${feedVersion ? `-${feedVersion}` : ""}.ics`;

  function upsertConnection(conn: Connection, running: boolean) {
    f.me.connections = [...f.me.connections.filter((c) => c.platform !== conn.platform), conn];
    f.sources = [
      ...f.sources.filter((s) => s.platform !== conn.platform),
      {
        platform: conn.platform,
        connection_status: "active",
        last_sync_at: conn.last_sync_at ?? null,
        running,
        stale: false,
      },
    ];
    if (!running) return;
    setTimeout(() => {
      const at = new Date().toISOString();
      const source = f.sources.find((s) => s.platform === conn.platform);
      if (source) Object.assign(source, { running: false, last_sync_at: at });
      const c = f.me.connections.find((x) => x.platform === conn.platform);
      if (c) c.last_sync_at = at;
    }, firstSyncMs);
  }

  return [
    http.post(api("/connections/canvas"), async ({ request }) => {
      if (!authed(request)) return unauthorized();
      const body = (await request.json()) as CanvasConnectRequest;
      const token = (body.token ?? "").trim();
      if (!token || /bad|invalid/i.test(token)) {
        return errorResponse(400, "invalid_token", "Canvas rejected this token.");
      }
      if (/down|unavailable/i.test(token)) {
        return errorResponse(502, "platform_unavailable", "Canvas is not responding.", true);
      }
      const conn: Connection = {
        platform: "canvas",
        status: "active",
        expires_at: body.expires_at ?? new Date(Date.now() + 90 * DAY).toISOString(),
        last_sync_at: null,
        account_label: f.me.display_name ?? "Demo Student",
      };
      upsertConnection(conn, true);
      return HttpResponse.json(conn);
    }),

    http.post(api("/connections/:platform/login"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const platform = String(params.platform) as Platform;
      const loginId = crypto.randomUUID();
      logins.set(loginId, { platform, polls: 0 });
      return HttpResponse.json({ login_id: loginId, mode: "local", live_view_url: null });
    }),

    http.get(api("/connections/:platform/login/:loginId"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const login = logins.get(String(params.loginId));
      if (!login) return HttpResponse.json({ state: "expired", error: null });
      login.polls += 1;
      if (login.polls <= pendingPolls) return HttpResponse.json({ state: "pending", error: null });
      upsertConnection({ platform: login.platform, status: "active", last_sync_at: null }, true);
      logins.delete(String(params.loginId));
      return HttpResponse.json({ state: "succeeded", error: null });
    }),

    http.delete(api("/connections/:platform"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const platform = String(params.platform);
      f.me.connections = f.me.connections.filter((c) => c.platform !== platform);
      f.sources = f.sources.filter((s) => s.platform !== platform);
      return new HttpResponse(null, { status: 204 });
    }),

    http.get(api("/models"), ({ request }) => (authed(request) ? HttpResponse.json(MOCK_MODELS) : unauthorized())),

    http.patch(api("/me"), async ({ request }) => {
      if (!authed(request)) return unauthorized();
      const body = (await request.json()) as MePatch;
      for (const [k, v] of Object.entries(body)) {
        if (v !== null && v !== undefined) Object.assign(f.me, { [k]: v });
      }
      return HttpResponse.json(f.me);
    }),

    http.delete(api("/me/data"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      f.me.connections = [];
      f.sources = [];
      return new HttpResponse(null, { status: 204 });
    }),

    http.get(api("/calendar/feed"), ({ request }) => (authed(request) ? HttpResponse.json({ url: feedUrl() }) : unauthorized())),

    http.post(api("/calendar/feed/rotate"), ({ request }) => {
      if (!authed(request)) return unauthorized();
      feedVersion += 1;
      return HttpResponse.json({ url: feedUrl() });
    }),
  ];
}
