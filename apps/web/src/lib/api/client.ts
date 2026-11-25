// Typed API client for the FastAPI backend (S02, S30).
// `api()` returns a singleton; AuthProvider calls `configureApi` with the Supabase token getter.
import { config } from "@/lib/config";
import { sessionRequest } from "./session-boundary";
import type {
  CalendarFeed,
  CanvasConnectRequest,
  Change,
  Citation,
  Connection,
  ConversationSummary,
  CourseDetail,
  CourseSummary,
  ErrorEnvelope,
  Item,
  ItemType,
  LoginStartResponse,
  LoginStatusResponse,
  Me,
  MePatch,
  Message,
  ModelsResponse,
  Platform,
  SourceStatus,
  Today,
  StudySet,
  StudySetSummary,
  StudyBlock,
} from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly details?: unknown;

  constructor(opts: { code: string; message: string; status: number; retryable: boolean; details?: unknown }) {
    super(opts.message);
    this.name = "ApiError";
    this.code = opts.code;
    this.status = opts.status;
    this.retryable = opts.retryable;
    this.details = opts.details;
  }
}

/** Abort errors can come from another realm (jsdom, workers), so check the name, not `instanceof`. */
export function isAbortError(e: unknown): boolean {
  return typeof e === "object" && e !== null && (e as { name?: unknown }).name === "AbortError";
}

export interface ApiConfig {
  baseUrl: string;
  getToken: () => Promise<string | null>;
  onUnauthorized: () => void | Promise<void>;
}

let current: ApiConfig = {
  baseUrl: config.apiUrl,
  getToken: async () => null,
  onUnauthorized: () => {},
};

export function configureApi(partial: Partial<ApiConfig>) {
  current = { ...current, ...partial };
}

export function getApiConfig(): ApiConfig {
  return current;
}

/** Converts a non-OK response into an ApiError (S02 error envelope when present). */
export async function toApiError(res: Response): Promise<ApiError> {
  const fallbackRetryable = res.status >= 500 || res.status === 429;
  let text = "";
  try {
    text = await res.text();
    const body = JSON.parse(text) as Partial<ErrorEnvelope>;
    if (body.error && typeof body.error.code === "string") {
      return new ApiError({
        code: body.error.code,
        message: body.error.message ?? res.statusText,
        status: res.status,
        retryable: Boolean(body.error.retryable),
        details: body.error.details,
      });
    }
  } catch {
    // not JSON: fall through
  }
  return new ApiError({
    code: res.status === 401 ? "unauthorized" : res.status >= 500 ? "internal" : `http_${res.status}`,
    message: text || res.statusText || `Request failed (${res.status})`,
    status: res.status,
    retryable: fallbackRetryable,
  });
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await current.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type Query = Record<string, string | number | boolean | undefined | null>;

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  opts: { query?: Query; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const cfg = current;
  const scope = sessionRequest(opts.signal);
  try {
    const url = new URL(`${cfg.baseUrl.replace(/\/$/, "")}${path}`);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
    const token = await cfg.getToken();
    scope.assertCurrent();
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    let res: Response;
    try {
      res = await fetch(url, {
        method, headers, body: opts.body === undefined ? undefined : JSON.stringify(opts.body), signal: scope.signal,
      });
    } catch (e) {
      scope.assertCurrent();
      if (isAbortError(e)) throw e;
      throw new ApiError({ code: "network", message: "Can't reach the server. Check your connection.", status: 0, retryable: true });
    }
    scope.assertCurrent();
    if (!res.ok) {
      const err = await toApiError(res);
      scope.assertCurrent();
      if (res.status === 401) await cfg.onUnauthorized();
      throw err;
    }
    if (res.status === 204) return undefined as T;
    const data = await res.json();
    scope.assertCurrent();
    return data as T;
  } finally {
    scope.close();
  }
}

export function createApiClient() {
  return {
    request,
    studySets: () => request<StudySetSummary[]>("GET", "/study-sets"),
    studySet: (id: string) => request<StudySet>("GET", `/study-sets/${encodeURIComponent(id)}`),
    decideBlocks: (block_ids: string[], approve: boolean) =>
      request<{ blocks: StudyBlock[] }>("POST", "/study-blocks/decision", { body: { block_ids, approve } }),
    me: () => request<Me>("GET", "/me"),
    today: (date?: string) => request<Today>("GET", "/today", { query: { date } }),
    courses: () => request<CourseSummary[]>("GET", "/courses"),
    course: (id: string) => request<CourseDetail>("GET", `/courses/${encodeURIComponent(id)}`),
    items: (q: { course_id?: string; type?: ItemType; from?: string; to?: string } = {}) =>
      request<Item[]>("GET", "/items", { query: q }),
    changes: (q: { since?: string; unseen?: boolean } = {}) => request<Change[]>("GET", "/changes", { query: q }),
    markChangesSeen: (ids: string[]) => request<void>("POST", "/changes/seen", { body: { ids } }),
    citations: (ids: number[]) => request<Citation[]>("GET", "/citations", { query: { ids: ids.join(",") } }),
    conversations: () => request<ConversationSummary[]>("GET", "/conversations"),
    conversation: (id: string) =>
      request<{ conversation: ConversationSummary; messages: Message[] }>("GET", `/conversations/${encodeURIComponent(id)}`),
    renameConversation: (id: string, title: string) =>
      request<ConversationSummary>("PATCH", `/conversations/${encodeURIComponent(id)}`, { body: { title } }),
    deleteConversation: (id: string) => request<void>("DELETE", `/conversations/${encodeURIComponent(id)}`),
    sync: (body: { platform?: Platform; course_id?: string } = {}) =>
      request<{ sync_run_ids: string[] }>("POST", "/sync", { body }),
    syncStatus: () => request<{ sources: SourceStatus[] }>("GET", "/sync/status"),
    // Account + connections (S31, S34)
    patchMe: (body: MePatch) => request<Me>("PATCH", "/me", { body }),
    deleteMyData: () => request<void>("DELETE", "/me/data"),
    models: () => request<ModelsResponse>("GET", "/models"),
    connectCanvas: (body: CanvasConnectRequest) => request<Connection>("POST", "/connections/canvas", { body }),
    startLogin: (platform: Platform) =>
      request<LoginStartResponse>("POST", `/connections/${encodeURIComponent(platform)}/login`),
    loginStatus: (platform: Platform, loginId: string) =>
      request<LoginStatusResponse>(
        "GET",
        `/connections/${encodeURIComponent(platform)}/login/${encodeURIComponent(loginId)}`,
      ),
    disconnect: (platform: Platform) => request<void>("DELETE", `/connections/${encodeURIComponent(platform)}`),
    calendarFeed: () => request<CalendarFeed>("GET", "/calendar/feed"),
    rotateCalendarFeed: () => request<CalendarFeed>("POST", "/calendar/feed/rotate"),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

const client = createApiClient();

/** The app's API client (S30). Reads auth + base URL from `configureApi`. */
export function api(): ApiClient {
  return client;
}
