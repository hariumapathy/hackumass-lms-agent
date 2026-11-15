// MSW in the browser for mock mode (NEXT_PUBLIC_API_MOCKS=1).
import { setupWorker } from "msw/browser";
import { createHandlers } from "./handlers";

export async function startMockWorker() {
  const worker = setupWorker(...createHandlers({ chatDelayMs: 150 }));
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
  return worker;
}
