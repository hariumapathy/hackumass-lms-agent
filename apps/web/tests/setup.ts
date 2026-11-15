import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { transferableAbortController } from "node:util";
import { afterEach, beforeEach, vi } from "vitest";
import { navState, routerMock } from "./next-navigation";

// next/navigation is mocked for every component test; tests set navState and assert on routerMock.
vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => navState.pathname,
  useSearchParams: () => new URLSearchParams(navState.search),
  useParams: () => navState.params,
  redirect: vi.fn(),
}));

/**
 * Test-environment glue: jsdom replaces AbortController, but Node's fetch (undici, also used by MSW)
 * only accepts Node AbortSignals. Translate the signal on every fetch. Installed per test, after MSW
 * has patched fetch in `beforeAll`, so it wraps MSW's interceptor. Browsers don't need this.
 */
let originalFetch: typeof fetch | undefined;

function withNodeSignal(inner: typeof fetch): typeof fetch {
  return (input, init) => {
    const signal = init?.signal;
    if (!signal) return inner(input, init);
    const controller = transferableAbortController();
    if (signal.aborted) controller.abort(signal.reason);
    else signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
    return inner(input, { ...init, signal: controller.signal });
  };
}

beforeEach(() => {
  navState.pathname = "/";
  navState.search = "";
  navState.params = {};
  for (const fn of Object.values(routerMock)) fn.mockReset();
  window.localStorage.clear();
  originalFetch = globalThis.fetch;
  globalThis.fetch = withNodeSignal(originalFetch);
});

afterEach(() => {
  cleanup();
  if (originalFetch) globalThis.fetch = originalFetch;
});
