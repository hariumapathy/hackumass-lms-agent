import { screen } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ExpiryBanner } from "@/components/layout/expiry-banner";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers } from "@/mocks/handlers";
import { renderWithProviders } from "./utils";

const DAY = 86_400_000;
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function withCanvasExpiry(msFromNow: number | null) {
  const f = buildFixtures();
  const canvas = f.me.connections.find((c) => c.platform === "canvas")!;
  canvas.expires_at = msFromNow === null ? null : new Date(Date.now() + msFromNow).toISOString();
  server.use(...createHandlers({ fixtures: f }));
}

// S34 rule 1: Canvas access expiry warning across the app when < 10 days (also on Today).
describe("S34 Canvas expiry banner", () => {
  it("S34-T06 shows a plain-language banner with a renew link under 10 days", async () => {
    withCanvasExpiry(4 * DAY + 3_600_000);
    renderWithProviders(<ExpiryBanner />);
    const banner = await screen.findByRole("status", { name: /canvas/i });
    expect(banner).toHaveTextContent(/canvas connection ends in 4 days/i);
    expect(banner).not.toHaveTextContent(/token/i);
    expect(screen.getByRole("link", { name: /renew canvas/i })).toHaveAttribute("href", "/onboarding?reconnect=canvas");
  });

  it("S34-T06 says it has ended once expired", async () => {
    withCanvasExpiry(-DAY);
    renderWithProviders(<ExpiryBanner />);
    expect(await screen.findByRole("status", { name: /canvas/i })).toHaveTextContent(/canvas connection has ended/i);
    expect(screen.getByRole("link", { name: /reconnect canvas/i })).toHaveAttribute("href", "/onboarding?reconnect=canvas");
  });

  it("S34-T06 stays hidden with 10+ days left or no expiry date", async () => {
    withCanvasExpiry(30 * DAY);
    const { unmount } = renderWithProviders(<ExpiryBanner />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("status", { name: /canvas/i })).not.toBeInTheDocument();
    unmount();

    withCanvasExpiry(null);
    renderWithProviders(<ExpiryBanner />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("status", { name: /canvas/i })).not.toBeInTheDocument();
  });
});
