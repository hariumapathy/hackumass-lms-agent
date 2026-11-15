import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { CitationCard } from "@/components/chat/citation-card";
import { configureApi } from "@/lib/api/client";
import type { Citation } from "@/lib/api/types";
import { MOCK_API_URL } from "@/mocks/handlers";
import { renderWithProviders } from "./utils";

const server = setupServer();
let auth: string | null = null;
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  URL.createObjectURL = vi.fn(() => "blob:http://localhost/pdf-1");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  server.resetHandlers();
  auth = null;
});
afterAll(() => server.close());

const FILE_ID = "5b0f0000-0000-4000-8000-000000000501";

function citation(over: Partial<Citation> = {}): Citation {
  return {
    chunk_id: 8812,
    title: "Lecture 7 - Greedy.pdf",
    kind: "slides",
    platform: "canvas",
    course_code: "COMPSCI 311",
    page: 14,
    start_s: null,
    end_s: null,
    url: "https://umamherst.instructure.com/courses/1/files/501",
    deep_link: "https://umamherst.instructure.com/courses/1/files/501",
    quote: "An exchange argument shows greedy stays ahead.",
    last_synced_at: new Date().toISOString(),
    status: "current",
    file_id: FILE_ID,
    ...over,
  };
}

function render(c: Citation) {
  const out = renderWithProviders(<CitationCard citation={c} />);
  configureApi({ baseUrl: MOCK_API_URL });
  return out;
}

describe("In-app file viewer (citations)", () => {
  it("FV-T01 a stored PDF opens in the app at the cited page, with the student's sign-in", async () => {
    server.use(
      http.get(`${MOCK_API_URL}/files/:id`, ({ request, params }) => {
        auth = request.headers.get("authorization");
        expect(params.id).toBe(FILE_ID);
        return new HttpResponse(new Uint8Array([37, 80, 68, 70]), { headers: { "Content-Type": "application/pdf" } });
      }),
    );
    render(citation());
    await userEvent.click(screen.getByRole("button", { name: /view/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Lecture 7 - Greedy.pdf")).toBeInTheDocument();
    const frame = await within(dialog).findByTitle(/lecture 7/i);
    expect(frame).toHaveAttribute("src", "blob:http://localhost/pdf-1#page=14");
    expect(auth).toBe("Bearer test-token");
    // The original is always one click away.
    expect(within(dialog).getByRole("link", { name: /open in canvas/i })).toHaveAttribute("href", citation().deep_link);
  });

  it("FV-T02 no stored file: no View button, Open source still works", () => {
    render(citation({ file_id: null }));
    expect(screen.queryByRole("button", { name: /view/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open source/i })).toHaveAttribute("href", citation().deep_link);
  });

  it("FV-T03 if the file can't be loaded, the viewer says so in plain words and links to Canvas", async () => {
    server.use(
      http.get(`${MOCK_API_URL}/files/:id`, () =>
        HttpResponse.json({ error: { code: "not_found", message: "File not found", retryable: false } }, { status: 404 }),
      ),
    );
    render(citation());
    await userEvent.click(screen.getByRole("button", { name: /view/i }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText(/couldn.t open this file here/i)).toBeInTheDocument());
    expect(within(dialog).queryByText(/not_found|404/i)).not.toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /open in canvas/i })).toBeInTheDocument();
  });
});
