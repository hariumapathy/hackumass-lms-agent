import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";
import { renderWithProviders } from "./utils";

describe("S00 smoke", () => {
  it("S00-T02 home page renders the app name", () => {
    renderWithProviders(<Home />, { auth: { status: "signed_out", user: null } });
    expect(screen.getByRole("heading", { name: /hackumass lms agent/i })).toBeInTheDocument();
  });
});
