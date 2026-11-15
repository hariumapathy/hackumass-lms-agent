"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Loading } from "@/components/states/states";
import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/lib/auth/auth-provider";
import { config } from "@/lib/config";

let browserQueryClient: QueryClient | undefined;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // S30 rule 3: retry only errors the API marks retryable.
        retry: (count, error) => error instanceof ApiError && error.retryable && count < 2,
      },
    },
  });
}

function getQueryClient() {
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

/** In mock mode, start MSW before anything fetches (S30 rule 5). */
function MockGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(!config.apiMocks);
  useEffect(() => {
    if (!config.apiMocks) return;
    let active = true;
    import("@/mocks/browser")
      .then((m) => m.startMockWorker())
      .then(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);
  if (!ready) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4">
        <Loading label="Loading…" />
      </div>
    );
  }
  return <>{children}</>;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <MockGate>
      <QueryClientProvider client={getQueryClient()}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </MockGate>
  );
}
