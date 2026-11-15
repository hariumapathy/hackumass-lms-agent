import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { TodayScreen } from "@/components/today/today-screen";
import { TodayView } from "@/components/today/today-view";
import type { Today } from "@/lib/api/types";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL } from "@/mocks/handlers";
import { setupServer } from "msw/node";
import { renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z"); // 10:00 AM in New York
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const noop = () => {};

function emptyToday(today: Today): Today {
  return { ...today, overdue: [], due_today: [], due_this_week: [], upcoming_exams: [], changes: [], new_posts: [] };
}

describe("S32 Today view", () => {
  it("S32-T04 renders each non-empty section with its items", () => {
    const f = buildFixtures(NOW);
    renderWithProviders(<TodayView today={f.today} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />);

    expect(screen.getByRole("heading", { level: 1, name: /today/i })).toBeInTheDocument();
    const overdue = screen.getByRole("region", { name: /overdue/i });
    expect(within(overdue).getByText("HW 6")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: /due today/i })).getByText("Lab 4")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: /this week/i })).getByText("HW5")).toBeInTheDocument();
    const exams = screen.getByRole("region", { name: /upcoming exams/i });
    expect(within(exams).getByText("Midterm 1")).toBeInTheDocument();
    expect(within(exams).getByText("CHANGED")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: /new announcements/i })).getByText("Office hours moved")).toBeInTheDocument();
  });

  it("S32-T04 hides empty sections", () => {
    const f = buildFixtures(NOW);
    const today = { ...f.today, overdue: [], new_posts: [] };
    renderWithProviders(<TodayView today={today} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />);
    expect(screen.queryByRole("region", { name: /overdue/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /new announcements/i })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /due today/i })).toBeInTheDocument();
  });

  it("S32-T04 shows the whole-page empty state when nothing is due", () => {
    const f = buildFixtures(NOW);
    renderWithProviders(
      <TodayView today={emptyToday(f.today)} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />,
    );
    expect(screen.getByText(/nothing due this week/i)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /due today/i })).not.toBeInTheDocument();
  });

  it("S32-T05 Mark seen calls the API and clears the banner and CHANGED badges", async () => {
    const f = buildFixtures(NOW);
    let seenBody: unknown = null;
    server.use(
      http.post(`${MOCK_API_URL}/changes/seen`, async ({ request }) => {
        seenBody = await request.clone().json();
        return undefined; // fall through to the default handler, which updates the fixtures
      }),
      ...createHandlers({ fixtures: f }),
    );
    renderWithProviders(<TodayScreen />);

    const banner = await screen.findByRole("region", { name: /changes/i });
    expect(within(banner).getByText(/midterm 1 moved/i)).toBeInTheDocument();
    const itemRow = (title: string) => screen.getByText(title).closest("li")!;
    expect(within(itemRow("Midterm 1")).getByText("CHANGED")).toBeInTheDocument();
    expect(within(itemRow("HW5")).getByText("CHANGED")).toBeInTheDocument();

    await userEvent.click(within(banner).getByRole("button", { name: /mark seen/i }));

    await waitFor(() => expect(screen.queryByRole("region", { name: /changes/i })).not.toBeInTheDocument());
    expect(seenBody).toEqual({ ids: f.changes.map((c) => c.id) });
    // Item badges clear; an edited post keeps its own badge (it isn't one of these changes).
    await waitFor(() => expect(within(itemRow("Midterm 1")).queryByText("CHANGED")).not.toBeInTheDocument());
    expect(within(itemRow("HW5")).queryByText("CHANGED")).not.toBeInTheDocument();
  });

  it("S32-T06 a needs_reconnect source shows a Reconnect link to onboarding", () => {
    const f = buildFixtures(NOW);
    renderWithProviders(<TodayView today={f.today} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />);
    const bar = screen.getByRole("region", { name: /sources/i });
    const reconnect = within(bar).getByRole("link", { name: /reconnect echo360/i });
    expect(reconnect).toHaveAttribute("href", "/onboarding?reconnect=echo360");
    expect(within(bar).queryByRole("link", { name: /reconnect canvas/i })).not.toBeInTheDocument();
  });

  it("S32-T07 source chips link to source_url in a new tab", () => {
    const f = buildFixtures(NOW);
    renderWithProviders(<TodayView today={f.today} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />);
    const lab = f.today.due_today.find((i) => i.title === "Lab 4")!;
    const row = screen.getByText("Lab 4").closest("li")!;
    for (const src of lab.sources) {
      const chip = within(row).getByRole("link", { name: new RegExp(src.platform, "i") });
      expect(chip).toHaveAttribute("href", src.source_url);
      expect(chip).toHaveAttribute("target", "_blank");
      expect(chip).toHaveAttribute("rel", expect.stringContaining("noopener"));
    }
  });
});
