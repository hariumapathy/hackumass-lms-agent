import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { ChatScreen } from "@/components/chat/chat-screen";
import { SessionsScreen } from "@/components/chat/sessions-screen";
import { AppShell } from "@/components/layout/app-shell";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL } from "@/mocks/handlers";
import { navState, routerMock } from "./next-navigation";
import { mockMatchMedia, renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z");
const CONV = "d0000000-0000-4000-8000-000000000001";
const TITLE = "What's on the CS 311 midterm?";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => server.resetHandlers(...createHandlers({ fixtures: buildFixtures(NOW) })));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const row = () => screen.getByRole("listitem", { name: TITLE });

describe("S36 sessions", () => {
  it("S36-T05 lists chats with their study sets, and saved sets without a chat", async () => {
    renderWithProviders(<SessionsScreen />);
    expect(screen.getByRole("heading", { name: "Sessions" })).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: TITLE });
    expect(link).toHaveAttribute("href", `/chat/${CONV}`);
    const item = row();
    expect(within(item).getByRole("link", { name: /Study plan/ })).toHaveAttribute(
      "href",
      "/study/e0000000-0000-4000-8000-000000000001",
    );
    expect(within(item).getByRole("link", { name: /Practice quiz/ })).toBeInTheDocument();
    expect(within(item).getByText(/Updated/)).toBeInTheDocument();
    const saved = screen.getByRole("region", { name: "Saved study sets" });
    expect(within(saved).getByText("CS 311 quick review")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /New chat/ })[0]).toHaveAttribute("href", "/chat");
  });

  it("S36-T05 empty state points to a new chat", async () => {
    server.use(
      http.get(`${MOCK_API_URL}/conversations`, () => HttpResponse.json([])),
      http.get(`${MOCK_API_URL}/study-sets`, () => HttpResponse.json([])),
    );
    renderWithProviders(<SessionsScreen />);
    expect(await screen.findByText("No sessions yet")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Saved study sets" })).not.toBeInTheDocument();
  });

  it("S36-T06 rename inline: Esc cancels, Enter saves", async () => {
    renderWithProviders(<SessionsScreen />);
    await screen.findByRole("link", { name: TITLE });
    await userEvent.click(screen.getByRole("button", { name: `Options for ${TITLE}` }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const box = screen.getByRole("textbox", { name: "Chat title" });
    expect(box).toHaveFocus();
    await userEvent.type(box, " draft{Escape}");
    expect(screen.getByRole("link", { name: TITLE })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: `Options for ${TITLE}` }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const again = screen.getByRole("textbox", { name: "Chat title" });
    await userEvent.clear(again);
    await userEvent.type(again, "Midterm prep{Enter}");
    expect(await screen.findByRole("link", { name: "Midterm prep" })).toBeInTheDocument();
  });

  it("S36-T06 delete asks first and keeps the study sets", async () => {
    renderWithProviders(<SessionsScreen />);
    await screen.findByRole("link", { name: TITLE });
    await userEvent.click(screen.getByRole("button", { name: `Options for ${TITLE}` }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("Delete this chat? Its flashcards and quizzes stay in Sessions."),
    ).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete chat" }));
    await waitFor(() => expect(screen.queryByRole("link", { name: TITLE })).not.toBeInTheDocument());
    const saved = screen.getByRole("region", { name: "Saved study sets" });
    expect(await within(saved).findByText("CS 311 midterm study plan")).toBeInTheDocument();
    expect(within(saved).getByText("CS 311 quick review")).toBeInTheDocument();
  });

  it("S36-T07 nav shows Sessions instead of Study (sidebar and phone tabs)", async () => {
    for (const desktop of [true, false]) {
      mockMatchMedia(desktop);
      navState.pathname = "/sessions";
      const view = renderWithProviders(
        <AppShell>
          <p>content</p>
        </AppShell>,
      );
      await act(async () => {});
      const nav = screen.getByRole("navigation", { name: desktop ? "Sidebar" : "Bottom tabs" });
      const link = within(nav).getByRole("link", { name: "Sessions" });
      expect(link).toHaveAttribute("href", "/sessions");
      expect(link).toHaveAttribute("aria-current", "page");
      expect(within(nav).queryByRole("link", { name: "Study" })).not.toBeInTheDocument();
      view.unmount();
    }
  });

  it("S36 a reopened chat shows the study sets made in it", async () => {
    mockMatchMedia(true);
    renderWithProviders(<ChatScreen conversationId={CONV} />);
    const main = await screen.findByText(/Midterm 1 covers everything/);
    expect(main).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /CS 311 midterm study plan/ })).toHaveAttribute(
      "href",
      "/study/e0000000-0000-4000-8000-000000000001",
    );
    expect(screen.getByRole("link", { name: /CS 311 dynamic programming quiz/ })).toBeInTheDocument();
  });

  it("S36-T06 deleting the open chat from the chat list starts a new chat", async () => {
    mockMatchMedia(true);
    renderWithProviders(<ChatScreen conversationId={CONV} />);
    const list = await screen.findByRole("complementary", { name: "Conversations" });
    await userEvent.click(await within(list).findByRole("button", { name: `Options for ${TITLE}` }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete chat" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/chat"));
    expect(within(list).queryByRole("link", { name: TITLE })).not.toBeInTheDocument();
  });

  it("S36 phone: New chat is one tap from an open chat", async () => {
    mockMatchMedia(false);
    renderWithProviders(<ChatScreen conversationId={CONV} />);
    await act(async () => {});
    await userEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(routerMock.push).toHaveBeenCalledWith("/chat");
  });
});
