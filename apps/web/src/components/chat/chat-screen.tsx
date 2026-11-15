"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, RotateCcw, Send, Square } from "lucide-react";
import { DESKTOP_QUERY, useMediaQuery } from "@/components/layout/use-media-query";
import { ErrorState, Loading } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, isAbortError } from "@/lib/api/client";
import { streamChat } from "@/lib/api/sse";
import type { Message } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { AssistantText } from "./assistant-text";
import { applyEvent, newTurn, settleStatus, type Turn } from "./chat-state";
import { StudySetCard } from "@/components/study/study-set-card";
import { ApprovalCard } from "./approval-card";
import { StatusList } from "./status-list";

const SUGGESTIONS = ["What's due this week?", "Did anything change?", "Prep me for my next exam"];

let turnCounter = 0;

/** Chat (S33 chat part). Pass a conversationId to continue a saved conversation. */
export function ChatScreen({ conversationId: initialId }: { conversationId?: string }) {
  const qc = useQueryClient();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState(initialId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState(() => searchParams.get("prefill") ?? "");
  const [running, setRunning] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  // Read inside send() so a retry right after run_started still uses the new conversation id.
  const conversationRef = useRef(initialId);

  const history = useQuery({
    queryKey: ["conversation", initialId],
    queryFn: () => api().conversation(initialId!),
    enabled: Boolean(initialId),
  });

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [turns]);

  const update = (key: string, fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t) => (t.key === key ? fn(t) : t)));

  async function send(text: string) {
    const message = text.trim();
    if (!message || controller.current) return;
    const key = `turn-${++turnCounter}`;
    setTurns((ts) => [...ts, newTurn(key, message)]);
    setInput("");
    setRunning(true);
    const ac = new AbortController();
    controller.current = ac;
    try {
      await streamChat(
        { conversation_id: conversationRef.current, message },
        {
          signal: ac.signal,
          onEvent: (ev) => {
            if (ev.type === "run_started") {
              const id = ev.data.conversation_id;
              if (conversationRef.current !== id) {
                conversationRef.current = id;
                setConversationId(id);
                // Give the new conversation its own URL without remounting the page.
                window.history.replaceState(null, "", `/chat/${id}`);
              }
            }
            update(key, (t) => applyEvent(t, ev));
          },
        },
      );
      // S30 edge case: the stream ended without done/error -> connection lost.
      update(key, (t) =>
        t.terminal
          ? settleStatus(t)
          : settleStatus({ ...t, phase: "error", error: { code: "connection_lost", message: "Lost the connection.", retryable: true } }),
      );
    } catch (e) {
      if (ac.signal.aborted || isAbortError(e)) {
        update(key, (t) => settleStatus({ ...t, phase: "stopped" }));
      } else {
        const error =
          e instanceof ApiError
            ? { code: e.code, message: e.message, retryable: e.retryable }
            : { code: "connection_lost", message: "Lost the connection.", retryable: true };
        update(key, (t) => settleStatus({ ...t, phase: "error", error }));
      }
    } finally {
      controller.current = null;
      setRunning(false);
      void qc.invalidateQueries({ queryKey: ["conversations"] });
    }
  }

  function retry(turn: Turn) {
    setTurns((ts) => ts.filter((t) => t.key !== turn.key));
    void send(turn.userText);
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(input);
    }
  };

  const saved: Message[] = history.data?.messages ?? [];
  const empty = saved.length === 0 && turns.length === 0;

  return (
    <div className="mx-auto flex h-full w-full max-w-5xl gap-6">
      {isDesktop && <ConversationList activeId={conversationId} />}
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
        {!isDesktop && (
          // Mobile: past chats fold away above the conversation (S33 rule 7, "sheet on mobile").
          <details className="rounded-md border px-3 py-2 text-sm">
            <summary className="cursor-pointer select-none font-medium">Past chats</summary>
            <ConversationList activeId={conversationId} className="w-full pt-2" />
          </details>
        )}

        <div className="flex flex-1 flex-col gap-6" aria-live="polite">
          {initialId && history.isPending && <Loading label="Loading conversation…" rows={2} />}
          {history.isError && <ErrorState error={history.error} onRetry={() => void history.refetch()} />}
          {saved.map((m) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.text} />
            ) : (
              <div key={m.id}>
                <AssistantText text={m.text} citations={m.citations} streaming={false} />
              </div>
            ),
          )}
          {turns.map((t) => (
            <TurnView key={t.key} turn={t} onRetry={() => retry(t)} />
          ))}
          {empty && !history.isPending && (
            <div className="flex flex-col items-start gap-3 py-8">
              <p className="text-muted-foreground">Ask anything about your courses. Answers cite your own course materials.</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button key={s} variant="outline" size="sm" onClick={() => void send(s)}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={onSubmit} className="sticky bottom-0 flex items-end gap-2 bg-background pb-2">
          <Textarea
            aria-label="Message"
            placeholder="Ask about deadlines, lectures, or exam prep…"
            value={input}
            disabled={running}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            className="min-h-11 resize-none"
          />
          {running ? (
            <Button type="button" variant="outline" onClick={() => controller.current?.abort()}>
              <Square aria-hidden /> Stop
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()}>
              <Send aria-hidden /> Send
            </Button>
          )}
        </form>
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return <div className="self-end rounded-2xl bg-primary px-4 py-2 whitespace-pre-wrap text-primary-foreground">{text}</div>;
}

function TurnView({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  const streaming = turn.phase === "streaming";
  const text = turn.finalText ?? turn.text;
  return (
    <>
      <UserBubble text={turn.userText} />
      <div className="flex flex-col gap-2">
        {turn.status.length > 0 &&
          (streaming ? (
            <StatusList items={turn.status} />
          ) : (
            <details className="text-sm text-muted-foreground">
              <summary className="cursor-pointer select-none">
                Checked {turn.status.length} {turn.status.length === 1 ? "source" : "sources"}
              </summary>
              <div className="pt-1">
                <StatusList items={turn.status} />
              </div>
            </details>
          ))}
        {text && <AssistantText text={text} citations={turn.citations} streaming={streaming} />}
        {turn.studySets.map((set) => <StudySetCard key={set.id} set={set} />)}
        {turn.approval && <ApprovalCard {...turn.approval} />}
        {turn.phase === "stopped" && <p className="text-sm text-muted-foreground">Stopped.</p>}
        {turn.error && (
          <div role="alert" className="flex flex-wrap items-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm">
            <AlertTriangle className="size-4 text-destructive" aria-hidden />
            <span>{turn.error.message}</span>
            {turn.error.retryable && (
              <Button size="xs" variant="outline" onClick={onRetry}>
                <RotateCcw aria-hidden /> Try again
              </Button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export function ConversationList({ activeId, className }: { activeId?: string; className?: string }) {
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: () => api().conversations() });
  return (
    <aside aria-label="Conversations" className={cn("flex w-56 shrink-0 flex-col gap-2", className)}>
      <Button asChild variant="outline" size="sm" className="justify-start">
        <Link href="/chat">
          <Plus aria-hidden /> New chat
        </Link>
      </Button>
      <ul className="flex flex-col gap-0.5">
        {(conversations.data ?? []).map((c) => (
          <li key={c.id}>
            <Link
              href={`/chat/${c.id}`}
              aria-current={c.id === activeId ? "page" : undefined}
              className={cn(
                "block truncate rounded-md px-3 py-1.5 text-sm hover:bg-accent",
                c.id === activeId && "bg-accent font-medium",
              )}
            >
              {c.title}
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
