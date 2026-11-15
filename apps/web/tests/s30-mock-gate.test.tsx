import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MockGate } from "@/components/states/mock-gate";

// S30 rule 5 (mock mode) + "never a dead end" (AGENTS.md UI rules).
describe("S30 mock mode gate", () => {
  it("S30-T08 renders the app right away when mock mode is off", () => {
    const start = vi.fn();
    render(
      <MockGate enabled={false} start={start}>
        <p>app</p>
      </MockGate>,
    );
    expect(screen.getByText("app")).toBeInTheDocument();
    expect(start).not.toHaveBeenCalled();
  });

  it("S30-T08 waits for the mock API, then renders the app", async () => {
    let resolve!: () => void;
    const start = vi.fn(() => new Promise<void>((r) => (resolve = r)));
    render(
      <MockGate enabled start={start}>
        <p>app</p>
      </MockGate>,
    );
    expect(screen.queryByText("app")).not.toBeInTheDocument();
    resolve();
    expect(await screen.findByText("app")).toBeInTheDocument();
  });

  it("S30-T08 shows a clear message and Try again when the mock API can't start", async () => {
    const start = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error("[MSW] Failed to register the Service Worker"))
      .mockResolvedValueOnce(undefined);
    render(
      <MockGate enabled start={start}>
        <p>app</p>
      </MockGate>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn.t start the demo/i);
    expect(alert).not.toHaveTextContent(/msw|service worker/i); // plain language

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(screen.getByText("app")).toBeInTheDocument());
    expect(start).toHaveBeenCalledTimes(2);
  });
});

describe("real mode cleans up a leftover mock worker", () => {
  it("unregisters only the MSW service worker", async () => {
    const { unregisterMockWorker } = await import("@/components/states/mock-gate");
    const gone: string[] = [];
    const reg = (url: string) => ({ active: { scriptURL: url }, unregister: async () => { gone.push(url); return true; } });
    const nav = {
      serviceWorker: {
        controller: null,
        getRegistrations: async () => [reg("http://localhost:3000/mockServiceWorker.js"), reg("http://localhost:3000/other-sw.js")],
      },
    } as unknown as Navigator;
    expect(await unregisterMockWorker(nav)).toBe(true);
    expect(gone).toEqual(["http://localhost:3000/mockServiceWorker.js"]);
  });
});
