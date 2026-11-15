"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MessageSquarePlus, Plus } from "lucide-react";
import { ErrorState } from "@/components/states/states";
import { StudySetCard } from "@/components/study/study-set-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { SessionRow } from "./session-row";

/** Sessions (S36): every chat with the flashcards / quizzes / plans made in it. Replaces "Study". */
export function SessionsScreen() {
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: () => api().conversations() });
  const studySets = useQuery({ queryKey: ["study-sets"], queryFn: () => api().studySets() });
  const saved = (studySets.data ?? []).filter((st) => !st.conversation_id);
  const list = conversations.data ?? [];

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-3xl font-semibold tracking-tight">Sessions</h1>
          <p className="text-sm text-muted-foreground">Your chats, with the flashcards, quizzes and plans you made in each.</p>
        </div>
        <Button asChild>
          <Link href="/chat">
            <Plus aria-hidden /> New chat
          </Link>
        </Button>
      </header>

      {conversations.isPending ? (
        <SessionsSkeleton />
      ) : conversations.isError ? (
        <ErrorState error={conversations.error} onRetry={() => void conversations.refetch()} />
      ) : list.length ? (
        <ul aria-label="Your sessions" className="flex flex-col gap-3">
          {list.map((c) => (
            <SessionRow key={c.id} conversation={c} />
          ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed bg-card/50 px-6 py-12 text-center">
          <span className="grid size-11 place-items-center rounded-xl bg-maroon text-white" aria-hidden>
            <MessageSquarePlus className="size-5" />
          </span>
          <p className="font-display text-xl font-semibold">No sessions yet</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Start a chat to ask about your classes. Flashcards, quizzes and study plans you make there show up here.
          </p>
          <Button asChild variant="outline" className="border-primary/30 text-primary">
            <Link href="/chat?prefill=Make%20me%20flashcards%20for%20my%20next%20exam">Make flashcards for my next exam</Link>
          </Button>
        </div>
      )}

      {saved.length > 0 && (
        <section aria-labelledby="saved-sets" className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <h2 id="saved-sets" className="text-lg font-semibold">
              Saved study sets
            </h2>
            <p className="text-sm text-muted-foreground">Kept from chats you deleted.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {saved.map((st) => (
              <StudySetCard key={st.id} set={st} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SessionsSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">Loading your sessions…</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-2 rounded-xl border bg-card p-4">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-3 w-24" />
          <div className="flex gap-2 pt-1">
            <Skeleton className="h-6 w-28 rounded-full" />
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
