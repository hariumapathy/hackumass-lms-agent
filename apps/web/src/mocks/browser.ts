// MSW in the browser for mock mode (NEXT_PUBLIC_API_MOCKS=1).
import { setupWorker } from "msw/browser";
import { createHandlers } from "./handlers";

type MockWorker = ReturnType<typeof setupWorker>;

let starting: Promise<MockWorker> | undefined;

/**
 * Starts the mock worker once per page. React Strict Mode runs effects twice in dev; a second worker
 * would keep its own mock state (live logins, seen changes), so requests would randomly hit one or the
 * other (S31 logins "expired" mid-flow). A failed start is cleared so "Try again" can retry.
 */
export function startMockWorker(): Promise<MockWorker> {
  starting ??= (async () => {
    const worker = setupWorker(...createHandlers({ chatDelayMs: 150 }));
    await worker.start({ onUnhandledRequest: "bypass", quiet: true });
    return worker;
  })().catch((e: unknown) => {
    starting = undefined;
    throw e;
  });
  return starting;
}
