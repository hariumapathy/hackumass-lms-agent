import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { SettingsScreen } from "@/components/settings/settings-screen";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL } from "@/mocks/handlers";
import { routerMock } from "./next-navigation";
import { renderWithProviders } from "./utils";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** Fresh fixtures per test; `spy` records method + path + body of every request, then falls through. */
function setup() {
  const calls: { method: string; path: string; body: unknown }[] = [];
  server.use(
    http.all(`${MOCK_API_URL}/*`, async ({ request }) => {
      const body = request.method === "GET" || request.method === "DELETE" ? null : await request.clone().json().catch(() => null);
      calls.push({ method: request.method, path: new URL(request.url).pathname, body });
      return undefined;
    }),
    ...createHandlers({ fixtures: buildFixtures() }),
  );
  return calls;
}

const card = (name: RegExp) => screen.getByRole("listitem", { name });

describe("S34 Settings", () => {
  it("S34-T01 shows each connection's status; Reconnect goes to onboarding", async () => {
    setup();
    renderWithProviders(<SettingsScreen />);
    const piazza = await screen.findByRole("listitem", { name: /piazza/i });
    expect(within(piazza).getByText(/needs reconnecting/i)).toBeInTheDocument();
    expect(within(piazza).getByRole("link", { name: /reconnect piazza/i })).toHaveAttribute("href", "/onboarding?reconnect=piazza");
    // Echo360 has no connector yet: never offered.
    expect(screen.queryByRole("listitem", { name: /echo360/i })).not.toBeInTheDocument();
    expect(within(card(/canvas/i)).getByText(/^connected/i)).toBeInTheDocument();
    expect(within(card(/canvas/i)).getByText(/access ends in \d+ days/i)).toBeInTheDocument();
    expect(within(card(/gradescope/i)).getByText(/^connected/i)).toBeInTheDocument();
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument(); // plain language
  });

  it("S34-T02 Disconnect asks for confirmation, then calls the API", async () => {
    const calls = setup();
    renderWithProviders(<SettingsScreen />);
    const gs = await screen.findByRole("listitem", { name: /gradescope/i });
    await userEvent.click(within(gs).getByRole("button", { name: /disconnect gradescope/i }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/stop updating gradescope/i);
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    await userEvent.click(within(dialog).getByRole("button", { name: /^disconnect$/i }));
    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ method: "DELETE", path: "/connections/gradescope" })));
    await waitFor(() => expect(within(card(/gradescope/i)).getByText(/not connected/i)).toBeInTheDocument());
  });

  it("S34-T03 Advanced lists AI options by tier; unavailable ones are disabled; choosing one saves it", async () => {
    const calls = setup();
    renderWithProviders(<SettingsScreen />);
    await userEvent.click(await screen.findByText("Advanced", { selector: "summary" }));

    const recommended = await screen.findByRole("radiogroup", { name: /recommended/i });
    const experimental = screen.getByRole("radiogroup", { name: /experimental/i });
    expect(within(recommended).getByRole("radio", { name: /gemini/i })).toBeInTheDocument();
    expect(within(recommended).getByRole("radio", { name: /claude/i })).toBeDisabled();
    expect(within(experimental).getByRole("radio", { name: /llama 3\.3/i })).toBeEnabled();
    expect(within(experimental).getByRole("radio", { name: /local/i })).toBeDisabled();
    expect(screen.getByText(/may skip tools or make mistakes/i)).toBeInTheDocument();

    await userEvent.click(within(recommended).getByRole("radio", { name: /gemini/i }));
    await waitFor(() =>
      expect(calls).toContainEqual(expect.objectContaining({ method: "PATCH", path: "/me", body: { model_choice: "gemini/gemini-default" } })),
    );
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });

  it("S34-T04 getting a new calendar link asks first, then shows the new link", async () => {
    const calls = setup();
    renderWithProviders(<SettingsScreen />);
    const cal = await screen.findByRole("region", { name: /calendar/i });
    await within(cal).findByText(/demo-feed\.ics/);
    expect(within(cal).getByRole("link", { name: /add to google calendar/i }).getAttribute("href")).toMatch(
      /^https:\/\/calendar\.google\.com\//,
    );

    await userEvent.click(within(cal).getByRole("button", { name: /get a new link/i }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/old link stops working/i);
    await userEvent.click(within(dialog).getByRole("button", { name: /get new link/i }));

    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ method: "POST", path: "/calendar/feed/rotate" })));
    expect(await within(cal).findByText(/demo-feed-1\.ics/)).toBeInTheDocument();
  });

  it("S34-T05 Delete my data needs DELETE typed, then deletes and signs out", async () => {
    const calls = setup();
    const { auth } = renderWithProviders(<SettingsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: /delete my data/i }));

    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: /delete everything/i });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByRole("textbox"), "delete");
    expect(confirm).toBeDisabled(); // must match exactly
    await userEvent.clear(within(dialog).getByRole("textbox"));
    await userEvent.type(within(dialog).getByRole("textbox"), "DELETE");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ method: "DELETE", path: "/me/data" })));
    await waitFor(() => expect(auth.signOut).toHaveBeenCalled());
    expect(routerMock.replace).toHaveBeenCalledWith("/");
  });
});
