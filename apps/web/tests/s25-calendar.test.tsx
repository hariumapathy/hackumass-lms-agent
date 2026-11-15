import { screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { CalendarButtons } from "@/components/connect/calendar-step";
import { renderWithProviders } from "./utils";

it("S25 local calendar offers a file instead of an unreachable Google subscription", () => {
  renderWithProviders(<CalendarButtons feedUrl="http://localhost:8000/calendar/private.ics" />);
  expect(screen.getByRole("link", { name: /download calendar/i })).toHaveAttribute("href", "http://localhost:8000/calendar/private.ics");
  expect(screen.queryByRole("link", { name: /add to google calendar/i })).not.toBeInTheDocument();
  expect(screen.getByText(/import.*google calendar/i)).toBeInTheDocument();
});
