import { beforeEach, describe, expect, it, vi } from "vitest";

const start = vi.fn();
vi.mock("msw/browser", () => ({ setupWorker: vi.fn(() => ({ start })) }));

// Strict Mode runs effects twice in dev; two workers would each keep their own mock state
// (e.g. live logins), so a login started on one "expires" on the other.
describe("S30 mock worker", () => {
  beforeEach(() => {
    vi.resetModules();
    start.mockReset();
  });

  it("S30-T09 starting mock mode twice registers only one worker", async () => {
    start.mockResolvedValue(undefined);
    const { startMockWorker } = await import("@/mocks/browser");
    const { setupWorker } = await import("msw/browser");
    await Promise.all([startMockWorker(), startMockWorker()]);
    await startMockWorker();
    expect(setupWorker).toHaveBeenCalledTimes(1);
    expect(start).toHaveBeenCalledTimes(1);
  });

  it("S30-T09 a failed start can be retried", async () => {
    start.mockRejectedValueOnce(new Error("no service worker")).mockResolvedValueOnce(undefined);
    const { startMockWorker } = await import("@/mocks/browser");
    await expect(startMockWorker()).rejects.toThrow();
    await expect(startMockWorker()).resolves.toBeDefined();
    expect(start).toHaveBeenCalledTimes(2);
  });
});
