import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CourseView } from "@/components/course/course-screen";
import { buildFixtures, COURSE_IDS } from "@/mocks/fixtures";
import { renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z");

describe("S32 course page", () => {
  it("S32-T09 course page lists upcoming and past items with the course color and source links", () => {
    const f = buildFixtures(NOW);
    const course = f.courseDetails[COURSE_IDS.cs311];
    renderWithProviders(<CourseView course={course} tz="America/New_York" now={NOW} />);

    expect(screen.getByRole("heading", { level: 1, name: /COMPSCI 311/ })).toBeInTheDocument();
    const upcoming = screen.getByRole("region", { name: "Upcoming" });
    const row = within(upcoming).getByText("Midterm 1").closest("li")!;
    const dot = row.querySelector('span[aria-hidden][style]') as HTMLElement;
    expect(dot.style.backgroundColor).toBe("rgb(124, 58, 237)"); // #7c3aed
    expect(within(row).getByRole("link", { name: /canvas/i })).toHaveAttribute("target", "_blank");
    expect(within(screen.getByRole("region", { name: "Past" })).getByText("HW4")).toBeInTheDocument();
  });
});
