"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { CheckCircle2, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import type { LoginStartResponse, Platform } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";

type State =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "waiting"; loginId: string; mode: LoginStartResponse["mode"]; liveViewUrl: string | null }
  | { kind: "connected" }
  | { kind: "expired" }
  | { kind: "failed"; message: string };

// The login id survives a page refresh so a 409 ("already in progress") can resume polling it (S31 errors table).
const storageKey = (platform: Platform) => `connect:login:${platform}`;
const storedLoginId = (platform: Platform) => window.sessionStorage.getItem(storageKey(platform));

function loginIdFromDetails(details: unknown): string | null {
  const id = (details as { login_id?: unknown } | null | undefined)?.login_id;
  return typeof id === "string" ? id : null;
}

interface Props {
  platform: Platform;
  onConnected: () => void;
  /** S31: poll the login every 2 s. */
  pollMs?: number;
}

/** Live login through our browser window (S13/S31 rule 3): start, poll until done, retry on expiry/failure. */
export function LiveLogin({ platform, onConnected, pollMs = 2000 }: Props) {
  const label = PLATFORM_LABEL[platform];
  const [state, setState] = useState<State>({ kind: "idle" });
  const loginId = state.kind === "waiting" ? state.loginId : null;
  const notifyConnected = useEffectEvent(() => onConnected());

  useEffect(() => {
    if (!loginId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const res = await api().loginStatus(platform, loginId);
        if (cancelled) return;
        if (res.state === "pending") {
          timer = setTimeout(tick, pollMs);
          return;
        }
        window.sessionStorage.removeItem(storageKey(platform));
        if (res.state === "succeeded") {
          setState({ kind: "connected" });
          notifyConnected();
        } else if (res.state === "expired") {
          setState({ kind: "expired" });
        } else {
          setState({ kind: "failed", message: "The login didn't finish." });
        }
      } catch {
        // A dropped request shouldn't end the login; keep checking.
        if (!cancelled) timer = setTimeout(tick, pollMs);
      }
    };
    timer = setTimeout(tick, pollMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [loginId, platform, pollMs]);

  const start = async () => {
    setState({ kind: "starting" });
    try {
      const res = await api().startLogin(platform);
      window.sessionStorage.setItem(storageKey(platform), res.login_id);
      setState({ kind: "waiting", loginId: res.login_id, mode: res.mode, liveViewUrl: res.live_view_url ?? null });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const existing = loginIdFromDetails(e.details) ?? storedLoginId(platform);
        if (existing) {
          setState({ kind: "waiting", loginId: existing, mode: "local", liveViewUrl: null });
          return;
        }
        setState({
          kind: "failed",
          message: "A login window is already open. Finish logging in there, or try again in a few minutes.",
        });
        return;
      }
      setState({ kind: "failed", message: `We couldn't start the ${label} login.` });
    }
  };

  if (state.kind === "connected") {
    return (
      <p className="inline-flex items-center gap-2 font-medium text-green-700 dark:text-green-400">
        <CheckCircle2 className="size-4" aria-hidden /> {label} connected
      </p>
    );
  }

  if (state.kind === "waiting") {
    return (
      <div className="flex flex-col gap-3">
        <p role="status" aria-live="polite" className="inline-flex items-center gap-2 font-medium">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Waiting for login…
        </p>
        {state.mode === "local" ? (
          <p className="text-sm text-muted-foreground">
            A browser window opened on this computer. Log in with your NetID and approve Duo.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Log in with your NetID and approve Duo.{" "}
            {state.liveViewUrl && (
              <a className="inline-flex items-center gap-1 underline" href={state.liveViewUrl} target="_blank" rel="noopener noreferrer">
                Open the UMass login <ExternalLink className="size-3" aria-hidden />
              </a>
            )}
          </p>
        )}
        <Button variant="outline" size="sm" className="w-fit" onClick={() => setState({ kind: "idle" })}>
          Cancel
        </Button>
      </div>
    );
  }

  if (state.kind === "expired" || state.kind === "failed") {
    return (
      <div role="alert" className="flex flex-col gap-2">
        <p className="text-sm">
          {state.kind === "expired" ? "The login timed out. No problem, just try again." : state.message}
        </p>
        <Button variant="outline" size="sm" className="w-fit" onClick={() => void start()}>
          <RefreshCw aria-hidden /> Try again
        </Button>
      </div>
    );
  }

  return (
    <Button className="w-fit" disabled={state.kind === "starting"} onClick={() => void start()}>
      {state.kind === "starting" && <Loader2 className="animate-spin" aria-hidden />}
      Connect {label}
    </Button>
  );
}
