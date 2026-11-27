import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "msw";
import { useEffect, useState } from "react";
import { afterAll, afterEach, beforeAll, expect, it, vi } from "vitest";
import { api, configureApi } from "@/lib/api/client";
import { streamChat } from "@/lib/api/sse";
import { AuthProvider } from "@/lib/auth/auth-provider";
import { useAuth } from "@/lib/auth/auth-context";
import type { AuthBackend, AuthSession } from "@/lib/auth/backend";
import { createMockServer } from "@/mocks/server";
import { MOCK_API_URL } from "@/mocks/handlers";

const server = createMockServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
const session = (id: string, token = id): AuthSession => ({ accessToken: token, user: { id, email: null } });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}
function backend(initial: AuthSession | null = session("A")) {
  let current = initial;
  let listener: (s: AuthSession | null) => void = () => {};
  const auth: AuthBackend = {
    mode: "supabase", getSession: vi.fn(async () => current),
    onChange: (cb) => { listener = cb; return () => { listener = () => {}; }; },
    signInWithGoogle: vi.fn(async () => {}), signInWithEmail: vi.fn(async () => {}),
    signIn: vi.fn(async () => {}), signOut: vi.fn(async () => { current = null; listener(null); }),
  };
  return { auth, emit(s: AuthSession | null) { current = s; listener(s); } };
}
let observedClient: QueryClient;
function Workspace() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  useEffect(() => { observedClient = queryClient; }, [queryClient]);
  const [draft, setDraft] = useState("");
  const result = useQuery({ queryKey: ["courses"], queryFn: () => api().request<{ owner: string }>("GET", "/private-test"), enabled: auth.status === "signed_in", staleTime: Infinity, retry: false });
  return <><p>user:{auth.user?.id ?? "none"}</p><p>{auth.status === "signed_in" ? result.data?.owner : "signed out"}</p><input aria-label="draft" value={draft} onChange={(e) => setDraft(e.target.value)} /><button onClick={() => void auth.signOut()}>Sign out</button></>;
}
function mount(auth: AuthBackend) {
  configureApi({ baseUrl: MOCK_API_URL });
  return render(<QueryClientProvider client={new QueryClient()}><AuthProvider backend={auth}><Workspace /></AuthProvider></QueryClientProvider>);
}
function ownResponse() {
  server.use(http.get(`${MOCK_API_URL}/private-test`, ({ request }) => Response.json({ owner: `private-${request.headers.get("Authorization")}` })));
}

it("S39-T01 warm cache and local state reset across identities", async () => {
  ownResponse(); const b = backend(); mount(b.auth);
  await screen.findByText("private-Bearer A");
  const old = observedClient;
  fireEvent.change(screen.getByLabelText("draft"), { target: { value: "A private draft" } });
  act(() => b.emit(session("B")));
  await screen.findByText("private-Bearer B");
  expect(screen.queryByText("private-Bearer A")).not.toBeInTheDocument();
  expect(screen.getByLabelText("draft")).toHaveValue("");
  expect(old.getQueryCache().getAll()).toHaveLength(0);
  expect(observedClient).not.toBe(old);
});

it("S39-T02 delayed A result cannot populate B cache", async () => {
  const pending = deferred<void>(); const started = deferred<void>();
  server.use(http.get(`${MOCK_API_URL}/private-test`, async ({ request }) => {
    if (request.headers.get("Authorization") === "Bearer A") { started.resolve(); await pending.promise; return Response.json({ owner: "old-A-private" }); }
    return Response.json({ owner: "new-B-private" });
  }));
  const b = backend(); mount(b.auth); await started.promise;
  act(() => b.emit(session("B"))); await screen.findByText("new-B-private");
  await act(async () => { pending.resolve(); });
  expect(observedClient.getQueryData(["courses"])).toEqual({ owner: "new-B-private" });
});

it("S39-T04 same-user refresh preserves cache and draft", async () => {
  ownResponse(); const b = backend(); mount(b.auth); await screen.findByText("private-Bearer A");
  const old = observedClient;
  fireEvent.change(screen.getByLabelText("draft"), { target: { value: "keep" } });
  act(() => b.emit(session("A", "refreshed")));
  expect(observedClient).toBe(old); expect(screen.getByLabelText("draft")).toHaveValue("keep");
  expect(await api().request("GET", "/private-test")).toEqual({ owner: "private-Bearer refreshed" });
});

it("S39-T05 late bootstrap cannot overwrite newer account event", async () => {
  ownResponse(); const b = backend(null); const initial = deferred<AuthSession | null>();
  vi.mocked(b.auth.getSession).mockImplementationOnce(() => initial.promise);
  mount(b.auth); act(() => b.emit(session("B")));
  await screen.findByText("private-Bearer B");
  await act(async () => initial.resolve(session("A")));
  expect(screen.getByText("user:B")).toBeInTheDocument();
});

it("S39-T06 sign-out hides data before provider completes", async () => {
  ownResponse(); const b = backend(); const done = deferred<void>();
  vi.mocked(b.auth.signOut).mockImplementation(() => done.promise);
  mount(b.auth); await screen.findByText("private-Bearer A");
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(screen.queryByText("private-Bearer A")).not.toBeInTheDocument());
  done.resolve();
});

it("S39-T06 pending logout cannot be undone by a refreshed old session", async () => {
  ownResponse(); const b = backend(); const done = deferred<void>();
  vi.mocked(b.auth.signOut).mockImplementation(() => done.promise);
  mount(b.auth); await screen.findByText("private-Bearer A");
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  act(() => b.emit(session("A", "refreshed-A")));
  expect(screen.getByText("user:none")).toBeInTheDocument();
  expect(screen.queryByText("private-Bearer A")).not.toBeInTheDocument();
  await act(async () => done.resolve());
});

it("S39-T05 explicit logout supersedes an initial session snapshot", async () => {
  ownResponse(); const b = backend(); const initial = deferred<AuthSession | null>();
  vi.mocked(b.auth.getSession).mockImplementationOnce(() => initial.promise);
  vi.mocked(b.auth.signOut).mockResolvedValue(undefined); // provider may emit no event
  mount(b.auth);
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await act(async () => initial.resolve(session("A")));
  expect(screen.getByText("user:none")).toBeInTheDocument();
});

it("S39-T03 a stale 401 cannot sign out the new account", async () => {
  ownResponse(); const b = backend(); mount(b.auth); await screen.findByText("private-Bearer A");
  const started = deferred<void>(); const release = deferred<void>();
  server.use(http.get(`${MOCK_API_URL}/old-request`, async () => { started.resolve(); await release.promise; return new Response("expired", { status: 401 }); }));
  const request = api().request("GET", "/old-request").catch((e: Error) => e);
  await started.promise; act(() => b.emit(session("B"))); await screen.findByText("private-Bearer B");
  release.resolve();
  expect(await request).toMatchObject({ name: "AbortError" });
  expect(b.auth.signOut).not.toHaveBeenCalled();
  expect(screen.getByText("user:B")).toBeInTheDocument();
});

it("S39-T07 old SSE text is fenced after switching accounts", async () => {
  ownResponse(); const b = backend(); mount(b.auth); await screen.findByText("private-Bearer A");
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const onEvent = vi.fn();
  server.use(http.post(`${MOCK_API_URL}/chat`, () => new Response(new ReadableStream({ start(c) { controller = c; c.enqueue(new TextEncoder().encode('event: status\ndata: {"label":"Working"}\n\n')); } }), { headers: { "Content-Type": "text/event-stream" } })));
  const request = streamChat({ message: "private question" }, { onEvent }).catch((e: Error) => e);
  await waitFor(() => expect(onEvent).toHaveBeenCalledTimes(1));
  act(() => b.emit(session("B"))); await screen.findByText("private-Bearer B");
  controller.enqueue(new TextEncoder().encode('event: text\ndata: {"delta":"A private answer"}\n\n')); controller.close();
  expect(await request).toMatchObject({ name: "AbortError" });
  expect(onEvent.mock.calls.some(([e]) => e.type === "text")).toBe(false);
});
