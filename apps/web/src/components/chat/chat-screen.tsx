"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, GraduationCap, Plus, RotateCcw, Send, Square } from "lucide-react";
import { DESKTOP_QUERY, useMediaQuery } from "@/components/layout/use-media-query";
import { ErrorState } from "@/components/states/states";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, isAbortError } from "@/lib/api/client";
import { streamChat } from "@/lib/api/sse";
import type { Message, StudySetSummary } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { AssistantText } from "./assistant-text";
import { applyEvent, newTurn, settleStatus, type Turn } from "./chat-state";
import { StudySetCard } from "@/components/study/study-set-card";
import { ApprovalCard } from "./approval-card";
import { StatusList } from "./status-list";
import { SessionRow } from "./session-row";

const SUGGESTIONS = ["What's due this week?", "Did anything change?", "Prep me for my next exam"];

let turnCounter = 0;

/** Chat (S33 chat part). Pass a conversationId to continue a saved conversation. */
export function ChatScreen({ conversationId: initialId }: { conversationId?: string }) {
  const qc = useQueryClient();
  const router = useRouter();
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

  const conversations = useQuery({ queryKey: ["conversations"], queryFn: () => api().conversations() });
  const history = useQuery({
    queryKey: ["conversation", initialId],
    queryFn: () => api().conversation(initialId!),
    enabled: Boolean(initialId),
  });

  // S35-T03: follow the stream only while the student is near the end; otherwise offer a jump.
  const [atEnd, setAtEnd] = useState(true);
  const atEndRef = useRef(true);
  useEffect(() => {
    const onScroll = () => {
      const near = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
      atEndRef.current = near;
      setAtEnd(near);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const jumpToEnd = () => endRef.current?.scrollIntoView?.({ block: "end", behavior: "smooth" });

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (atEndRef.current) endRef.current?.scrollIntoView?.({ block: "end" });
  }, [turns]);

  const update = (key: string, fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t) => (t.key === key ? fn(t) : t)));

  async function send(text: string) {
    const message = text.trim();
    if (!message || controller.current) return;
    const key = `turn-${++turnCounter}`;
    atEndRef.current = true; // sending a message always brings you to the answer
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

  /** S36: start over. On a saved chat's page go to /chat; on /chat just clear this screen. */
  function newChat() {
    controller.current?.abort();
    if (initialId) {
      router.push("/chat");
      return;
    }
    setTurns([]);
    setInput("");
    setConversationId(undefined);
    conversationRef.current = undefined;
    window.history.replaceState(null, "", "/chat");
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
  // S36: study sets made in this chat, so a reopened session shows its flashcards / quiz / plan again.
  const setsById = new Map<string, StudySetSummary>(
    (conversations.data?.find((c) => c.id === conversationId)?.study_sets ?? []).map((st) => [st.id, st]),
  );
  const empty = saved.length === 0 && turns.length === 0;

  return (
    // Fill the screen minus the app shell padding (phone: pt-6 + pb-24; desktop: py-8) so the composer sits at the bottom.
    <div className="mx-auto flex min-h-[calc(100dvh-7.5rem)] w-full max-w-5xl gap-6 md:min-h-[calc(100dvh-4rem)]">
      {isDesktop && <ConversationList activeId={conversationId} onNewChat={newChat} />}
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <header className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-3xl font-semibold tracking-tight">Chat</h1>
            <p className="text-sm text-muted-foreground">Answers come from your own classes, with a link to every source.</p>
          </div>
          {!isDesktop && (
            <Button variant="outline" size="sm" className="shrink-0" onClick={newChat}>
              <Plus aria-hidden /> New chat
            </Button>
          )}
        </header>
        {!isDesktop && (
          // Mobile: past chats fold away above the conversation (S33 rule 7, "sheet on mobile").
          <details className="rounded-xl border bg-card px-3 py-2 text-sm shadow-xs">
            <summary className="cursor-pointer select-none font-medium">Past chats</summary>
            <ConversationList activeId={conversationId} onNewChat={newChat} className="w-full pt-2" showNewChat={false} />
          </details>
        )}

        <div className="flex flex-1 flex-col gap-6" aria-live="polite">
          {initialId && history.isPending && <ConversationSkeleton />}
          {history.isError && <ErrorState error={history.error} onRetry={() => void history.refetch()} />}
          {saved.map((m) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.text} />
            ) : (
              <AssistantRow key={m.id}>
                <AssistantText text={m.text} citations={m.citations} streaming={false} />
                {m.study_set_ids.map((id) => setsById.get(id)).filter((st) => st !== undefined).map((st) => (
                  <StudySetCard key={st.id} set={st} />
                ))}
              </AssistantRow>
            ),
          )}
          {turns.map((t) => (
            <TurnView key={t.key} turn={t} onRetry={() => retry(t)} />
          ))}
          {empty && !(initialId && history.isPending) && (
            <div className="flex flex-col items-start gap-4 rounded-2xl border bg-card px-5 py-6 shadow-xs">
              <span className="grid size-10 place-items-center rounded-xl bg-maroon text-white" aria-hidden>
                <GraduationCap className="size-5" />
              </span>
              <div className="flex flex-col gap-1">
                <p className="font-display text-xl font-semibold">What can I help you study?</p>
                <p className="text-sm text-muted-foreground">Ask anything about your courses. Answers cite your own course materials.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    className="rounded-full border-primary/30 text-primary hover:bg-accent hover:text-accent-foreground"
                    onClick={() => void send(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Phone: stick above the fixed bottom tab bar (4rem); desktop: to the bottom edge. */}
        <div className="sticky bottom-16 flex flex-col gap-2 bg-gradient-to-t from-background via-background to-transparent pt-4 pb-3 md:bottom-0">
          {!atEnd && (turns.length > 0 || saved.length > 0) && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="self-center rounded-full bg-card shadow-md"
              onClick={jumpToEnd}
            >
              <ArrowDown aria-hidden /> Jump to latest
            </Button>
          )}
          <form
            onSubmit={onSubmit}
            className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-md focus-within:border-primary/50 focus-within:ring-[3px] focus-within:ring-ring/20"
          >
            <Textarea
              aria-label="Message"
              placeholder="Ask about deadlines, lectures, or exam prep…"
              value={input}
              disabled={running}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              className="min-h-11 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
            />
            {running ? (
              <Button type="button" variant="outline" className="rounded-xl" onClick={() => controller.current?.abort()}>
                <Square aria-hidden /> Stop
              </Button>
            ) : (
              <Button type="submit" className="rounded-xl" disabled={!input.trim()}>
                <Send aria-hidden /> Send
              </Button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-primary px-4 py-2.5 whitespace-pre-wrap text-primary-foreground shadow-sm">
      {text}
    </div>
  );
}

/** Assistant side: small avatar + content at a readable width. */
function AssistantRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-maroon text-white" aria-hidden>
        <GraduationCap className="size-4" />
      </span>
      <div className="flex min-w-0 max-w-[68ch] flex-1 flex-col gap-2.5">{children}</div>
    </div>
  );
}

function TurnView({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  const streaming = turn.phase === "streaming";
  const text = turn.finalText ?? turn.text;
  return (
    <>
      <UserBubble text={turn.userText} />
      <AssistantRow>
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
          <div role="alert" className="flex flex-wrap items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
            <AlertTriangle className="size-4 text-destructive" aria-hidden />
            <span>{turn.error.message}</span>
            {turn.error.retryable && (
              <Button size="xs" variant="outline" onClick={onRetry}>
                <RotateCcw aria-hidden /> Try again
              </Button>
            )}
          </div>
        )}
      </AssistantRow>
    </>
  );
}

export function ConversationList({
  activeId,
  className,
  onNewChat,
  showNewChat = true,
}: {
  activeId?: string;
  className?: string;
  onNewChat?: () => void;
  showNewChat?: boolean;
}) {
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: () => api().conversations() });
  const list = conversations.data ?? [];
  return (
    <aside aria-label="Conversations" className={cn("flex w-60 shrink-0 flex-col gap-2 pt-1", className)}>
      <span className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Your chats</span>
      {showNewChat &&
        (onNewChat ? (
          <Button variant="outline" size="sm" className="justify-start" onClick={onNewChat}>
            <Plus aria-hidden /> New chat
          </Button>
        ) : (
          <Button asChild variant="outline" size="sm" className="justify-start">
            <Link href="/chat">
              <Plus aria-hidden /> New chat
            </Link>
          </Button>
        ))}
      {conversations.isPending ? (
        <div role="status" className="flex flex-col gap-1.5 px-1 pt-1">
          <span className="sr-only">Loading your chats…</span>
          <Skeleton className="h-7 w-full" />
          <Skeleton className="h-7 w-4/5" />
          <Skeleton className="h-7 w-3/5" />
        </div>
      ) : list.length === 0 ? (
        <p className="px-3 text-sm text-muted-foreground">Your chats will show up here.</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {list.map((c) => (
            <SessionRow
              key={c.id}
              conversation={c}
              variant="compact"
              active={c.id === activeId}
              onDeleted={c.id === activeId ? onNewChat : undefined}
            />
          ))}
        </ul>
      )}
      <Link
        href="/sessions"
        className="rounded px-3 pt-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-2"
      >
        See all sessions and study sets
      </Link>
    </aside>
  );
}

function ConversationSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-5">
      <span className="sr-only">Loading conversation…</span>
      <Skeleton className="h-10 w-2/3 self-end rounded-2xl" />
      <div className="flex gap-3">
        <Skeleton className="size-8 shrink-0 rounded-full" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      </div>
    </div>
  );
}
