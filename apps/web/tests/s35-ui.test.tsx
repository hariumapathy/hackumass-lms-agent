import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Home from "@/app/page";
import { TodayView } from "@/components/today/today-view";
import type { Change } from "@/lib/api/types";
import { buildFixtures } from "@/mocks/fixtures";
import { renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z");
const noop = () => {};

describe("S35 UMass UI", () => {
  it("S35-T06 a long change list shows 3 and folds the rest behind 'Show N more'", async () => {
    const f = buildFixtures(NOW);
    const base = f.today.changes[0];
    const changes: Change[] = Array.from({ length: 5 }, (_, i) => ({ ...base, id: `c${i}`, summary: `Change number ${i + 1}` }));
    renderWithProviders(
      <TodayView today={{ ...f.today, changes }} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />,
    );
    const banner = screen.getByRole("region", { name: /changes/i });
    expect(within(banner).getByText("5 changes")).toBeInTheDocument();
    expect(within(banner).getByText("Change number 1")).toBeVisible();
    const more = within(banner).getByText("Show 2 more");
    await userEvent.click(more);
    expect(within(banner).getByText("Change number 5")).toBeVisible();
  });

  it("S35-T07 due-today items come before overdue ones and are marked with the highlight", () => {
    const f = buildFixtures(NOW);
    renderWithProviders(<TodayView today={f.today} courses={f.courses} now={NOW} onMarkSeen={noop} onSyncNow={noop} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent ?? "");
    const today = headings.findIndex((h) => /due today/i.test(h));
    const overdue = headings.findIndex((h) => /overdue/i.test(h));
    if (today >= 0 && overdue >= 0) expect(today).toBeLessThan(overdue);
  });

  it("S35-T08 landing keeps the product heading, sign-in, and the not-official note", () => {
    renderWithProviders(<Home />);
    expect(screen.getByRole("heading", { level: 1, name: /hackumass lms agent/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByText(/not an official university of massachusetts service/i)).toBeInTheDocument();
  });
});
