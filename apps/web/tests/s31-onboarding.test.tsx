import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { calendarLinks } from "@/components/connect/calendar-links";
import { CalendarStep } from "@/components/connect/calendar-step";
import { CanvasStep } from "@/components/connect/canvas-step";
import { LiveLogin } from "@/components/connect/live-login";
import { OnboardingFlow } from "@/components/connect/onboarding-flow";
import { saveProgress } from "@/components/connect/progress";
import { buildFixtures, type Fixtures } from "@/mocks/fixtures";
import { createHandlers, errorResponse, MOCK_API_URL } from "@/mocks/handlers";
import { navState, routerMock } from "./next-navigation";
import { renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z");
const api = (path: string) => `${MOCK_API_URL}${path}`;
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => window.sessionStorage.clear());

/** A brand-new account: nothing connected yet. */
function newStudent(): Fixtures {
  const f = buildFixtures(NOW);
  f.me.connections = [];
  f.sources = [];
  return f;
}

/** Canvas linked (and its first load done); Gradescope + Echo360 not connected. */
function canvasOnly(): Fixtures {
  const f = buildFixtures(NOW);
  f.me.connections = f.me.connections.filter((c) => c.platform === "canvas");
  f.sources = f.sources.filter((s) => s.platform === "canvas");
  return f;
}

const FAST = { loginPollMs: 10, statusPollMs: 10 };

async function paste(input: HTMLElement, text: string) {
  await userEvent.click(input);
  await userEvent.paste(text);
}

describe("S31 onboarding", () => {
  it("S31-T01 Canvas step: pasting a good code links Canvas and shows the account name", async () => {
    let body: unknown = null;
    server.use(
      http.post(api("/connections/canvas"), async ({ request }) => {
        body = await request.clone().json();
        return undefined;
      }),
      ...createHandlers({ fixtures: newStudent() }),
    );
    const onLinked = vi.fn();
    renderWithProviders(<CanvasStep onLinked={onLinked} onContinue={() => {}} />);

    expect(screen.getByRole("heading", { name: /link your canvas/i })).toBeInTheDocument();
    const settings = screen.getByRole("link", { name: /open my canvas settings/i });
    expect(settings).toHaveAttribute("href", "https://umamherst.instructure.com/profile/settings");
    expect(settings).toHaveAttribute("target", "_blank");

    await paste(screen.getByLabelText(/paste your canvas code/i), "  1234~abcdefghijklmnop  ");

    expect(await screen.findByText(/canvas linked for demo student/i)).toBeInTheDocument();
    expect(body).toEqual({ token: "1234~abcdefghijklmnop" });
    expect(onLinked).toHaveBeenCalledWith(expect.objectContaining({ platform: "canvas", status: "active" }));
    expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument();
  });

  it("S31-T01 Canvas step: invalid_token shows the friendly error and lets them paste again", async () => {
    server.use(
      http.post(api("/connections/canvas"), () => errorResponse(400, "invalid_token", "Canvas rejected this token.")),
      ...createHandlers({ fixtures: newStudent() }),
    );
    renderWithProviders(<CanvasStep onLinked={() => {}} onContinue={() => {}} />);

    const input = screen.getByLabelText(/paste your canvas code/i);
    await paste(input, "not-the-whole-code");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That code didn't work. Make sure you copied the whole thing (it's long!).",
    );
    expect(screen.getByLabelText(/paste your canvas code/i)).not.toHaveAttribute("readonly");
  });

  it("S31-T01 Canvas step: Canvas being down shows a retryable message", async () => {
    server.use(
      http.post(api("/connections/canvas"), () =>
        errorResponse(502, "platform_unavailable", "Canvas is not responding.", true),
      ),
      ...createHandlers({ fixtures: newStudent() }),
    );
    renderWithProviders(<CanvasStep onLinked={() => {}} onContinue={() => {}} />);
    await paste(screen.getByLabelText(/paste your canvas code/i), "1234~abcdefghijklmnop");
    expect(await screen.findByRole("alert")).toHaveTextContent(/canvas isn't responding, try again in a minute/i);
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("S31-T02 live login: pending -> succeeded updates the UI", async () => {
    let polls = 0;
    server.use(
      http.post(api("/connections/gradescope/login"), () =>
        HttpResponse.json({ login_id: "11111111-1111-4111-8111-111111111111", mode: "local", live_view_url: null }),
      ),
      http.get(api("/connections/gradescope/login/:id"), () => {
        polls += 1;
        return HttpResponse.json({ state: polls < 3 ? "pending" : "succeeded", error: null });
      }),
    );
    const onConnected = vi.fn();
    renderWithProviders(<LiveLogin platform="gradescope" pollMs={10} onConnected={onConnected} />);

    await userEvent.click(screen.getByRole("button", { name: /connect gradescope/i }));
    expect(await screen.findByText(/waiting for login/i)).toBeInTheDocument();
    expect(screen.getByText(/a browser window opened on this computer/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();

    expect(await screen.findByText(/gradescope connected/i)).toBeInTheDocument();
    expect(onConnected).toHaveBeenCalledTimes(1);
    expect(polls).toBe(3);
  });

  it("S31-T02 live login: expired shows Try again, which starts a new login", async () => {
    let starts = 0;
    server.use(
      http.post(api("/connections/echo360/login"), () => {
        starts += 1;
        return HttpResponse.json({ login_id: `2222222${starts}-2222-4222-8222-222222222222`, mode: "local" });
      }),
      http.get(api("/connections/echo360/login/:id"), () => HttpResponse.json({ state: "expired", error: null })),
    );
    renderWithProviders(<LiveLogin platform="echo360" pollMs={10} onConnected={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: /connect echo360/i }));
    expect(await screen.findByText(/the login timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(starts).toBe(2));
  });

  it("S31-T02 live login: a 409 (login already open) resumes polling the existing login", async () => {
    const existing = "33333333-3333-4333-8333-333333333333";
    window.sessionStorage.setItem("connect:login:gradescope", existing);
    const polled: string[] = [];
    server.use(
      http.post(api("/connections/gradescope/login"), () =>
        errorResponse(409, "conflict", "A login is already in progress."),
      ),
      http.get(api("/connections/gradescope/login/:id"), ({ params }) => {
        polled.push(String(params.id));
        return HttpResponse.json({ state: "succeeded", error: null });
      }),
    );
    renderWithProviders(<LiveLogin platform="gradescope" pollMs={10} onConnected={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /connect gradescope/i }));
    expect(await screen.findByText(/gradescope connected/i)).toBeInTheDocument();
    expect(polled).toEqual([existing]);
  });

  it("S31-T03 a new student can skip the optional steps and reach the last step, then go to Today", async () => {
    server.use(...createHandlers({ fixtures: newStudent() }));
    renderWithProviders(<OnboardingFlow {...FAST} />);

    await userEvent.click(await screen.findByRole("button", { name: /get started/i }));
    await paste(await screen.findByLabelText(/paste your canvas code/i), "1234~abcdefghijklmnop");
    await userEvent.click(await screen.findByRole("button", { name: /continue/i }));

    expect(await screen.findByRole("heading", { name: /gradescope and echo360/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /skip for now/i }));

    expect(await screen.findByRole("heading", { name: /calendar/i })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /^skip$/i }));

    expect(await screen.findByRole("heading", { name: /getting your classes|you're all set/i })).toBeInTheDocument();
    const goToday = await screen.findByRole("button", { name: /go to today/i });
    await waitFor(() => expect(goToday).toBeEnabled());
    await userEvent.click(goToday);
    expect(routerMock.push).toHaveBeenCalledWith("/today");
  });

  it("S31-T03 Go to Today stays disabled until the first Canvas load finishes", async () => {
    const f = canvasOnly();
    f.sources[0] = { ...f.sources[0], last_sync_at: null, running: true };
    saveProgress("u-test", { welcomed: true, skipped: ["gradescope", "echo360"], calendar: "skipped" });
    server.use(...createHandlers({ fixtures: f }));
    renderWithProviders(<OnboardingFlow {...FAST} />);

    expect(await screen.findByRole("heading", { name: /getting your classes/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /go to today/i })).toBeDisabled();

    f.sources[0] = { ...f.sources[0], last_sync_at: NOW.toISOString(), running: false };
    await waitFor(() => expect(screen.getByRole("button", { name: /go to today/i })).toBeEnabled());
  });

  it("S31-T04 refresh resumes at the first incomplete step", async () => {
    server.use(...createHandlers({ fixtures: newStudent() }));
    const first = renderWithProviders(<OnboardingFlow {...FAST} />);
    expect(await screen.findByRole("button", { name: /get started/i })).toBeInTheDocument();
    first.unmount();

    server.use(...createHandlers({ fixtures: canvasOnly() }));
    const second = renderWithProviders(<OnboardingFlow {...FAST} />);
    expect(await screen.findByRole("heading", { name: /gradescope and echo360/i })).toBeInTheDocument();
    second.unmount();

    saveProgress("u-test", { welcomed: true, skipped: ["gradescope", "echo360"] });
    renderWithProviders(<OnboardingFlow {...FAST} />);
    expect(await screen.findByRole("heading", { name: /calendar/i })).toBeInTheDocument();
  });

  it("S31-T05 reconnect mode jumps to that platform and returns to settings after success", async () => {
    navState.search = "reconnect=echo360";
    server.use(...createHandlers({ fixtures: buildFixtures(NOW) }));
    renderWithProviders(<OnboardingFlow {...FAST} />);

    expect(await screen.findByRole("heading", { name: /reconnect echo360/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /connect gradescope/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /connect echo360/i }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/settings"));
  });

  it("S31-T05 reconnect mode for Canvas returns to settings after a new code is linked", async () => {
    navState.search = "reconnect=canvas";
    server.use(...createHandlers({ fixtures: buildFixtures(NOW) }));
    renderWithProviders(<OnboardingFlow {...FAST} />);

    await paste(await screen.findByLabelText(/paste your canvas code/i), "1234~abcdefghijklmnop");
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/settings"));
  });

  it("S31-T07 no onboarding screen uses jargon (token outside the Canvas instructions, sync, MCP, model, API)", async () => {
    const JARGON = /\b(tokens?|sync\w*|mcp|models?|api)\b/i;
    const visibleText = () => {
      const clone = document.body.cloneNode(true) as HTMLElement;
      clone.querySelectorAll("[data-canvas-instructions]").forEach((n) => n.remove());
      return clone.textContent ?? "";
    };
    const f = newStudent();
    server.use(...createHandlers({ fixtures: f, chatDelayMs: 0 }));
    renderWithProviders(<OnboardingFlow loginPollMs={60_000} statusPollMs={10} />);

    await screen.findByRole("button", { name: /get started/i });
    expect(visibleText()).not.toMatch(JARGON);
    await userEvent.click(screen.getByRole("button", { name: /get started/i }));

    const input = await screen.findByLabelText(/paste your canvas code/i);
    expect(visibleText()).not.toMatch(JARGON);
    await paste(input, "1234~abcdefghijklmnop");
    await screen.findByText(/canvas linked/i);
    expect(visibleText()).not.toMatch(JARGON);
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));

    await userEvent.click(await screen.findByRole("button", { name: /connect gradescope/i }));
    await screen.findByText(/waiting for login/i);
    expect(visibleText()).not.toMatch(JARGON);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    await userEvent.click(screen.getByRole("button", { name: /skip for now/i }));

    await screen.findByRole("link", { name: /add to google calendar/i });
    expect(visibleText()).not.toMatch(JARGON);
    await userEvent.click(screen.getByRole("button", { name: /^skip$/i }));

    await screen.findByRole("button", { name: /go to today/i });
    expect(visibleText()).not.toMatch(JARGON);
  });

  it("S31-T08 calendar step renders Google / Apple / Outlook links built from the feed URL", async () => {
    const feed = "https://api.example.edu/calendar/secret-abc.ics";
    server.use(http.get(api("/calendar/feed"), () => HttpResponse.json({ url: feed })));
    const onDone = vi.fn();
    renderWithProviders(<CalendarStep onDone={onDone} />);

    const google = await screen.findByRole("link", { name: /add to google calendar/i });
    expect(google).toHaveAttribute(
      "href",
      `https://calendar.google.com/calendar/r?cid=${encodeURIComponent("webcal://api.example.edu/calendar/secret-abc.ics")}`,
    );
    expect(google).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: /apple calendar/i })).toHaveAttribute(
      "href",
      "webcal://api.example.edu/calendar/secret-abc.ics",
    );
    expect(screen.getByRole("link", { name: /outlook/i }).getAttribute("href")).toContain(encodeURIComponent(feed));
    expect(screen.queryByText(feed)).not.toBeInTheDocument();
    expect(screen.getByText(/can take a few hours to show up in google calendar/i)).toBeInTheDocument();

    await userEvent.click(google);
    expect(await screen.findByText(/added/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(onDone).toHaveBeenCalledWith("added");
  });

  it("S31-T08 calendarLinks also works for an http feed URL", () => {
    const url = "http://localhost:8000/calendar/demo-feed.ics";
    const links = calendarLinks(url);
    expect(links.apple).toBe("webcal://localhost:8000/calendar/demo-feed.ics");
    expect(links.google).toBe(`https://calendar.google.com/calendar/r?cid=${encodeURIComponent(links.apple)}`);
    expect(links.outlook).toBe(
      `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(url)}&name=${encodeURIComponent("Class deadlines")}`,
    );
  });
});
