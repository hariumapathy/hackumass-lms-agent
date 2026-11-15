// MSW for Node (Vitest). Each test file creates its own server with fresh fixtures.
import { setupServer } from "msw/node";
import { createHandlers, type HandlerOptions } from "./handlers";

export function createMockServer(opts: HandlerOptions = {}) {
  return setupServer(...createHandlers(opts));
}
