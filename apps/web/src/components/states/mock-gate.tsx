"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { config } from "@/lib/config";
import { Loading } from "./states";

const defaultStart = () => import("@/mocks/browser").then((m) => m.startMockWorker()).then(() => undefined);

type Phase = "starting" | "ready" | "failed";

/**
 * Mock mode (S30 rule 5): start MSW before anything fetches. If the browser can't run it
 * (service workers blocked, private window, embedded browser), say so with one action instead of
 * spinning forever.
 */
export function MockGate({
  enabled = config.apiMocks,
  start = defaultStart,
  children,
}: {
  enabled?: boolean;
  start?: () => Promise<void>;
  children: ReactNode;
}) {
  const [phase, setPhase] = useState<Phase>(enabled ? "starting" : "ready");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    start().then(
      () => active && setPhase("ready"),
      (e: unknown) => {
        console.error("Mock API failed to start", e);
        if (active) setPhase("failed");
      },
    );
    return () => {
      active = false;
    };
  }, [enabled, start, attempt]);

  if (phase === "ready") return <>{children}</>;
  if (phase === "failed") {
    return (
      <div role="alert" className="mx-auto flex w-full max-w-md flex-col items-center gap-3 px-4 py-24 text-center">
        <AlertTriangle className="size-6 text-amber-600" aria-hidden />
        <p className="font-medium">We couldn&apos;t start the demo in this browser.</p>
        <p className="text-sm text-muted-foreground">Try again, or open the app in Chrome or Edge.</p>
        <Button
          variant="outline"
          onClick={() => {
            setPhase("starting");
            setAttempt((n) => n + 1);
          }}
        >
          <RefreshCw aria-hidden /> Try again
        </Button>
      </div>
    );
  }
  return (
    <div className="mx-auto w-full max-w-3xl px-4">
      <Loading label="Loading…" />
    </div>
  );
}
