import { screen, waitFor } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { http } from "msw";
import { afterAll, afterEach, beforeAll, expect, it } from "vitest";
import { setupServer } from "msw/node";
import { SyncMonitor } from "@/components/layout/sync-monitor";
import { api } from "@/lib/api/client";
import { buildFixtures } from "@/mocks/fixtures";
import { MOCK_API_URL } from "@/mocks/handlers";
import { renderWithProviders } from "./utils";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

it("S32-T10 a completed background import refreshes cached Today, courses, and profile", async () => {
  const fixtures = buildFixtures();
  let finished = false;
  let polls = 0;
  const reads = { today: 0, courses: 0, me: 0 };
  server.use(
    http.get(`${MOCK_API_URL}/sync/status`, () => {
      polls++;
      return Response.json({ sources: [{ platform: "canvas", connection_status: "active", running: !finished, stale: false, last_sync_at: finished ? "2026-11-15T02:00:00Z" : null }] });
    }),
    http.get(`${MOCK_API_URL}/today`, () => { reads.today++; return Response.json(fixtures.today); }),
    http.get(`${MOCK_API_URL}/courses`, () => { reads.courses++; return Response.json(fixtures.courses); }),
    http.get(`${MOCK_API_URL}/me`, () => { reads.me++; return Response.json(fixtures.me); }),
  );
  function CachedDashboard() {
    const today = useQuery({ queryKey: ["today"], queryFn: () => api().today(), staleTime: Infinity });
    useQuery({ queryKey: ["courses"], queryFn: () => api().courses(), staleTime: Infinity });
    useQuery({ queryKey: ["me"], queryFn: () => api().me(), staleTime: Infinity });
    return <><SyncMonitor pollMs={20} /><p>{today.data ? "Ready" : "Loading"}</p></>;
  }
  renderWithProviders(<CachedDashboard />);
  await screen.findByText("Ready");
  await waitFor(() => expect(polls).toBeGreaterThan(0));
  finished = true;
  await waitFor(() => {
    expect(reads.today).toBeGreaterThan(1);
    expect(reads.courses).toBeGreaterThan(1);
    expect(reads.me).toBeGreaterThan(1);
  });
});
