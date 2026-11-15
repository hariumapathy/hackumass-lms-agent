"use client";

import { useRef, useState, type ClipboardEvent, type FormEvent, type ReactNode } from "react";
import { CheckCircle2, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api/client";
import type { Connection } from "@/lib/api/types";

export const CANVAS_SETTINGS_URL = "https://umass.instructure.com/profile/settings";

/** Friendly copy for every error POST /connections/canvas can return (S31 errors table, S02 codes). */
export function canvasErrorMessage(e: unknown): { message: string; retryable: boolean } {
  if (e instanceof ApiError) {
    if (e.code === "invalid_token" || e.code === "validation_error" || e.status === 422) {
      return { message: "That code didn't work. Make sure you copied the whole thing (it's long!).", retryable: false };
    }
    if (e.code === "platform_unavailable" || e.code === "network" || e.retryable || e.status >= 500) {
      return { message: "Canvas isn't responding, try again in a minute.", retryable: true };
    }
    if (e.code === "unauthorized") return { message: "Please sign in again.", retryable: false };
  }
  return { message: "Something went wrong. Try again.", retryable: true };
}

type State =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "linked"; connection: Connection }
  | { kind: "error"; message: string; retryable: boolean };

const mask = (code: string) => "•".repeat(Math.min(code.length, 32));

interface Props {
  onLinked: (connection: Connection) => void;
  onContinue?: () => void;
  /** Reconnect mode uses a shorter heading. */
  heading?: string;
}

/** Guided Canvas link (S31 rule 1–2): the only step that needs the student to copy something. */
export function CanvasStep({ onLinked, onContinue, heading = "Link your Canvas (about 1 minute)" }: Props) {
  const [code, setCode] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const lastTried = useRef("");

  const submit = async (raw: string) => {
    const value = raw.trim();
    if (!value || state.kind === "checking") return;
    lastTried.current = value;
    setCode(value);
    setState({ kind: "checking" });
    try {
      const connection = await api().connectCanvas({ token: value });
      setState({ kind: "linked", connection });
      onLinked(connection);
    } catch (e) {
      setState({ kind: "error", ...canvasErrorMessage(e) });
      setCode("");
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    void submit(e.clipboardData.getData("text"));
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void submit(code);
  };

  const busy = state.kind === "checking" || state.kind === "linked";

  return (
    <section aria-labelledby="canvas-step-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="canvas-step-heading" className="text-2xl font-semibold tracking-tight">
          {heading}
        </h1>
        <p className="text-muted-foreground">We can only read your Canvas. We never submit or change anything.</p>
      </div>

      <ol
        data-canvas-instructions
        aria-label="How to get your Canvas code"
        className="flex flex-col gap-4 rounded-lg border bg-muted/30 p-4"
      >
        <Instruction n={1}>
          <Button asChild variant="outline" className="w-fit">
            <a href={CANVAS_SETTINGS_URL} target="_blank" rel="noopener noreferrer">
              Open my Canvas settings <ExternalLink aria-hidden />
            </a>
          </Button>
        </Instruction>
        <Instruction n={2}>
          Scroll to <em>Approved Integrations</em>, click <strong>+ New Access Token</strong>, type{" "}
          <em>Study Agent</em> as the purpose, pick the <strong>latest</strong> expiry date, then click{" "}
          <strong>Generate Token</strong>.
        </Instruction>
        <Instruction n={3}>Copy the long code Canvas shows you and paste it below.</Instruction>
      </ol>

      <form onSubmit={onSubmit} className="flex flex-col gap-2">
        <label htmlFor="canvas-code" className="font-medium">
          Paste your Canvas code
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="canvas-code"
            className="h-12 font-mono text-base"
            autoComplete="off"
            spellCheck={false}
            placeholder="Paste here"
            value={busy ? mask(code) : code}
            readOnly={busy}
            aria-invalid={state.kind === "error" || undefined}
            aria-describedby="canvas-code-status"
            onPaste={onPaste}
            onChange={(e) => setCode(e.target.value)}
          />
          {state.kind !== "linked" && (
            <Button type="submit" size="lg" className="h-12" disabled={busy || !code.trim()}>
              Link Canvas
            </Button>
          )}
        </div>
        <div id="canvas-code-status" aria-live="polite" className="min-h-6 text-sm">
          {state.kind === "checking" && (
            <span role="status" className="inline-flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Checking your code…
            </span>
          )}
          {state.kind === "linked" && (
            <span className="inline-flex items-center gap-2 font-medium text-green-700 dark:text-green-400">
              <CheckCircle2 className="size-4" aria-hidden />
              Canvas linked{state.connection.account_label ? ` for ${state.connection.account_label}` : ""}.
            </span>
          )}
        </div>
        {state.kind === "error" && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
            {state.message}
            {state.retryable && (
              <Button type="button" variant="outline" size="sm" onClick={() => void submit(lastTried.current)}>
                <RefreshCw aria-hidden /> Try again
              </Button>
            )}
          </div>
        )}
      </form>

      {state.kind === "linked" && onContinue && (
        <Button size="lg" className="w-fit" onClick={onContinue}>
          Continue
        </Button>
      )}
    </section>
  );
}

function Instruction({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden
        className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
      >
        {n}
      </span>
      {/* Plain block (not flex): a flex column would put every inline word/em/strong on its own line. */}
      <div className="min-w-0 pt-0.5 leading-relaxed">{children}</div>
    </li>
  );
}
