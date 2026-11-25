/** S39: cancel and fence network work when the authenticated identity changes. */
let generation = 0;
const active = new Set<AbortController>();

export function invalidateSessionRequests() {
  generation += 1;
  for (const controller of active) controller.abort();
  active.clear();
}

export function sessionRequest(signal?: AbortSignal) {
  const expected = generation;
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort, { once: true });
  active.add(controller);
  return {
    signal: controller.signal,
    assertCurrent() {
      if (expected !== generation || controller.signal.aborted) {
        const error = new Error("The request was canceled.");
        error.name = "AbortError";
        throw error;
      }
    },
    close() {
      signal?.removeEventListener("abort", abort);
      active.delete(controller);
    },
  };
}
