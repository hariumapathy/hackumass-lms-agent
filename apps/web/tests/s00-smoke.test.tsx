import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("S00 smoke", () => {
  it("S00-T02 home page renders the app name", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: /hackumass lms agent/i })).toBeInTheDocument();
  });
});
