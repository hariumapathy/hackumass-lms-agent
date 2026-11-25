import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";

/** A cache belongs to one AuthProvider identity boundary, never the whole browser. */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (count, error) => error instanceof ApiError && error.retryable && count < 2,
      },
    },
  });
}
