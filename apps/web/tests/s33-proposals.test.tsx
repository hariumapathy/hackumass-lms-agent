import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ChatScreen } from "@/components/chat/chat-screen";
import { buildFixtures, scriptedChat } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL, sseResponse } from "@/mocks/handlers";
import type { ChatEvent, StudySet, StudyBlock } from "@/lib/api/types";
import { renderWithProviders } from "./utils";

const f = buildFixtures();
const set: StudySet = { id: "quiz-1", type: "quiz", title: "Midterm practice", created_at: new Date().toISOString(), payload: { questions: [{ prompt: "Test" }] } };
const block: StudyBlock = { id: "block-1", title: "Review memoization", start_at: "2026-11-16T21:00:00Z", end_at: "2026-11-16T22:00:00Z", status: "proposed" };
const server = setupServer(...createHandlers({ fixtures: f }));
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function showProposals() {
  const events = scriptedChat("study-conversation", f);
  const additions: ChatEvent[] = [
    { type: "study_set", data: { study_set: set } },
    { type: "approval_required", data: { blocks: [block], summary: "Add a study session?" } },
  ];
  events.splice(events.findIndex((e) => e.type === "citations"), 0, ...additions);
  server.use(http.post(`${MOCK_API_URL}/chat`, () => sseResponse(events)));
  renderWithProviders(<ChatScreen />);
  await userEvent.type(screen.getByRole("textbox", { name: "Message" }), "Prep me{Enter}");
  await screen.findByText("Add a study session?");
}

describe("S33 streamed study cards and approvals", () => {
  it("S33 runtime: study_set and approval_required render after the streamed answer", async () => {
    await showProposals();
    expect(screen.getByRole("link", { name: /Practice quiz/ })).toHaveAttribute("href", "/study/quiz-1");
    expect(within(screen.getByRole("region", { name: "Study sessions" })).getByText("Review memoization")).toBeInTheDocument();
  });
  it.each([true, false])("S33-T09 Add/Skip sends one decision and locks (approve=%s)", async (approve) => {
    const bodies: unknown[] = [];
    server.use(http.post(`${MOCK_API_URL}/study-blocks/decision`, async ({ request }) => {
      bodies.push(await request.json());
      await delay(80);
      return HttpResponse.json({ blocks: [{ ...block, status: approve ? "approved" : "declined" }] });
    }));
    await showProposals();
    await userEvent.dblClick(screen.getByRole("button", { name: approve ? "Add" : "Skip" }));
    await screen.findByText(approve ? "Added. They'll show up in your calendar app on its next refresh." : "Skipped.");
    expect(bodies).toEqual([{ block_ids: [block.id], approve }]);
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Skip" })).toBeDisabled();
  });
  it("S33-T09 failed decision can be retried without claiming success", async () => {
    server.use(http.post(`${MOCK_API_URL}/study-blocks/decision`, () => HttpResponse.json({}, { status: 503 })));
    await showProposals();
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await screen.findByText("Couldn't save your choice. Try again.");
    await waitFor(() => expect(screen.getByRole("button", { name: "Add" })).toBeEnabled());
    expect(screen.queryByText(/^Added\./)).not.toBeInTheDocument();
  });
});
