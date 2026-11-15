import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { AssistantText } from "@/components/chat/assistant-text";
import { ChatScreen } from "@/components/chat/chat-screen";
import { CitationCard } from "@/components/chat/citation-card";
import { StatusList } from "@/components/chat/status-list";
import type { ChatEvent } from "@/lib/api/types";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL, sseResponse } from "@/mocks/handlers";
import { mockMatchMedia, renderWithProviders } from "./utils";

const NOW = new Date("2026-11-14T15:00:00Z");
const f = buildFixtures(NOW);
const [cSlides, cTranscript, cPiazza] = f.citations; // 8812 current, 9930 changed, 4410 removed

const server = setupServer(...createHandlers({ fixtures: f }));
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const started = (id = "conv-1"): ChatEvent => ({
  type: "run_started",
  data: { run_id: "r", conversation_id: id, user_message_id: "u" },
});

async function send(text: string) {
  const box = screen.getByRole("textbox", { name: /message/i });
  await userEvent.type(box, `${text}{Enter}`);
}

describe("S33 chat UI", () => {
  it("S33-T01 status checklist shows started, done and failed states", () => {
    renderWithProviders(
      <StatusList
        items={[
          { id: "a", label: "Checking your CS 311 exams…", state: "started" },
          { id: "b", label: "Searching slides…", state: "done" },
          { id: "c", label: "Pulling the lecture…", state: "failed" },
        ]}
      />,
    );
    const row = (label: string) => screen.getByText(label).closest("li")!;
    expect(within(row("Checking your CS 311 exams…")).getByLabelText("running")).toBeInTheDocument();
    expect(within(row("Searching slides…")).getByLabelText("done")).toBeInTheDocument();
    expect(within(row("Pulling the lecture…")).getByLabelText("failed")).toBeInTheDocument();
  });

  it("S33-T02 streaming text hides markers behind placeholder dots, including a half-received marker", () => {
    renderWithProviders(
      <AssistantText text="Memoization trades memory for time [cite:chunk_8812] and more [cite:chu" citations={null} streaming />,
    );
    expect(screen.getByText(/memoization trades memory for time/i)).toBeInTheDocument();
    expect(screen.queryByText(/\[cite/)).not.toBeInTheDocument();
    expect(screen.getAllByLabelText("Citation pending")).toHaveLength(1);
  });

  it("S33-T03 citations turn valid markers into numbered chips and remove dropped ones", () => {
    renderWithProviders(
      <AssistantText
        text="A [cite:chunk_8812] B [cite:chunk_77] C [cite:chunk_9930] again [cite:chunk_8812]"
        citations={[cSlides, cTranscript]}
        streaming={false}
      />,
    );
    const chips = screen.getAllByRole("button", { name: /^citation \d/i });
    expect(chips.map((c) => c.textContent)).toEqual(["1", "2", "1"]);
    expect(screen.queryByText(/\[cite/)).not.toBeInTheDocument();
    expect(screen.queryByText(/77/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Citation pending")).not.toBeInTheDocument();
  });

  it("S33-T03 the scripted mock stream ends with chips for exactly the valid citations", async () => {
    mockMatchMedia(true);
    renderWithProviders(<ChatScreen />);
    await send("Prep me for the CS 311 midterm");
    await screen.findByText(/rewatch the nov 11 lecture/i);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /^citation \d/i })).toHaveLength(3));
    expect(screen.getByText(/searching lecture slides and piazza/i)).toBeInTheDocument();
  });

  it("S33-T04 done.final_text replaces the streamed text", async () => {
    mockMatchMedia(true);
    server.use(
      http.post(`${MOCK_API_URL}/chat`, () =>
        sseResponse([
          started(),
          { type: "text", data: { delta: "Draft answr with a typo" } },
          { type: "citations", data: { citations: [], dropped: [] } },
          { type: "done", data: { run_id: "r", message_id: "m", final_text: "Final answer, cleaned." } },
        ]),
      ),
    );
    renderWithProviders(<ChatScreen />);
    await send("hello");
    expect(await screen.findByText("Final answer, cleaned.")).toBeInTheDocument();
    expect(screen.queryByText(/draft answr/i)).not.toBeInTheDocument();
  });

  it("S33-T05 Retry on a retryable error resends the same message", async () => {
    mockMatchMedia(true);
    const bodies: unknown[] = [];
    let call = 0;
    server.use(
      http.post(`${MOCK_API_URL}/chat`, async ({ request }) => {
        bodies.push(await request.json());
        call += 1;
        if (call === 1) {
          return sseResponse([
            started(),
            { type: "text", data: { delta: "Partial ans" } },
            { type: "error", data: { code: "model_error", message: "The model is unavailable.", retryable: true } },
          ]);
        }
        return sseResponse([
          started(),
          { type: "text", data: { delta: "Recovered." } },
          { type: "citations", data: { citations: [], dropped: [] } },
          { type: "done", data: { run_id: "r2", message_id: "m2", final_text: "Recovered." } },
        ]);
      }),
    );
    renderWithProviders(<ChatScreen />);
    await send("What's due this week?");

    expect(await screen.findByText(/the model is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText("Partial ans")).toBeInTheDocument(); // partial text stays visible
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText("Recovered.")).toBeInTheDocument();
    expect(bodies).toHaveLength(2);
    expect((bodies[1] as { message: string }).message).toBe("What's due this week?");
    expect((bodies[1] as { conversation_id?: string }).conversation_id).toBe("conv-1");
  });

  it("S33-T06 citation card shows title, quote, and a status badge for changed/removed sources", () => {
    const { rerender } = renderWithProviders(<CitationCard citation={cTranscript} />);
    expect(screen.getByText("Lecture Nov 11")).toBeInTheDocument();
    expect(screen.getByText(/23:41/)).toBeInTheDocument(); // start_s 1421 -> 23:41
    expect(screen.getByText(/changed since/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open source/i })).toHaveAttribute("href", cTranscript.deep_link);

    rerender(<CitationCard citation={cPiazza} />);
    expect(screen.getByText(/removed/i)).toBeInTheDocument();

    rerender(<CitationCard citation={cSlides} />);
    expect(screen.getByText(/p\. 12/)).toBeInTheDocument();
    expect(screen.queryByText(/changed since|removed/i)).not.toBeInTheDocument();
  });

  it("S33-T10 Stop aborts the stream", async () => {
    mockMatchMedia(true);
    let signal: AbortSignal | undefined;
    server.use(
      http.post(`${MOCK_API_URL}/chat`, ({ request }) => {
        signal = request.signal;
        return sseResponse([started(), { type: "text", data: { delta: "Thinking about it" } }], { hang: true });
      }),
    );
    renderWithProviders(<ChatScreen />);
    await send("hello");
    await screen.findByText("Thinking about it");

    await userEvent.click(screen.getByRole("button", { name: /stop/i }));

    expect(await screen.findByText(/stopped/i)).toBeInTheDocument();
    expect(signal?.aborted).toBe(true);
    expect(screen.getByRole("textbox", { name: /message/i })).toBeEnabled();
  });
});
