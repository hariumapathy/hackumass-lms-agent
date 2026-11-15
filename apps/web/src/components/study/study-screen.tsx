"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { Citation, StudySet } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CitationCard } from "@/components/chat/citation-card";
import { Empty, ErrorState, Loading } from "@/components/states/states";
import { StudySetCard } from "./study-set-card";
import { parsePayload, type Payload, type Day, type Question, type Card } from "./payload";

export function StudyList() {
  const query = useQuery({ queryKey: ["study-sets"], queryFn: () => api().studySets() });
  return <div className="space-y-5"><h1 className="text-3xl font-semibold tracking-tight">Study sets</h1>
    {query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.data.length ? <div className="grid gap-3 sm:grid-cols-2">{query.data.map(set => <StudySetCard key={set.id} set={set} />)}</div> : <Empty title="No study sets yet" action={<Link href="/chat" className="underline">Ask for a study set</Link>} />}
  </div>;
}

export function StudyDetail({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["study-set", id], queryFn: () => api().studySet(id) });
  const payload = query.data ? parsePayload(query.data.type, query.data.payload) : null;
  return <div className="mx-auto max-w-3xl space-y-5">
    <Link href="/study" className="text-sm underline">All study sets</Link>
    {query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : <><h1 className="text-3xl font-semibold tracking-tight">{query.data.title}</h1>{payload ? <StudyContent key={id} set={query.data} payload={payload} /> : <ErrorState error={new Error("This study set couldn't be opened.")} />}</>}
  </div>;
}

function StudyContent({ set, payload }: { set: StudySet; payload: Payload }) {
  const items = payload.type === "plan" ? payload.days.flatMap(d => d.tasks) : payload.type === "quiz" ? payload.questions : payload.cards;
  const allIds = [...new Set(items.flatMap(i => i.chunk_ids))];
  const saved = set.payload.citations as Record<string, Citation> | undefined;
  const resolved = allIds.map(id => saved?.[id]).filter((c): c is Citation => !!c && typeof c.chunk_id === "number");
  const missing = allIds.filter(id => !resolved.some(c => c.chunk_id === id));
  const query = useQuery({ queryKey: ["study-citations", set.id, missing], queryFn: () => api().citations(missing), enabled: missing.length > 0 });
  const citations = [...resolved, ...(query.data ?? [])];
  return <>
    {query.isError && <ErrorState error={new Error("Sources couldn't be loaded.")} onRetry={() => void query.refetch()} />}
    {payload.type === "plan" ? <Plan id={set.id} days={payload.days} citations={citations} /> : payload.type === "quiz" ? <Quiz questions={payload.questions} citations={citations} /> : <Flashcards cards={payload.cards} citations={citations} />}
  </>;
}

function Sources({ ids, citations }: { ids: number[]; citations: Citation[] }) {
  return <span className="inline-flex flex-wrap gap-1">{ids.map(id => citations.find(c => c.chunk_id === id)).filter((c): c is Citation => !!c).map((c, i) => <Popover key={c.chunk_id}>
    <PopoverTrigger aria-label={`Citation ${i + 1}: ${c.title}`} className="rounded border px-2 py-1 text-xs hover:bg-accent">{i + 1}</PopoverTrigger>
    <PopoverContent className="w-80 max-w-[90vw]"><CitationCard citation={c} /></PopoverContent>
  </Popover>)}</span>;
}

function Plan({ id, days, citations }: { id: string; days: Day[]; citations: Citation[] }) {
  const storageKey = `study-plan:${id}`;
  const [checked, setChecked] = useState<string[]>(() => {
    try { const v: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]"); return Array.isArray(v) ? v.filter((s): s is string => typeof s === "string") : []; } catch { return []; }
  });
  const [saveError, setSaveError] = useState(false);
  function toggle(key: string) {
    const next = checked.includes(key) ? checked.filter(k => k !== key) : [...checked, key];
    setChecked(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); setSaveError(false); } catch { setSaveError(true); }
  }
  return <div className="space-y-4">{saveError && <p role="status">Your browser couldn&apos;t save progress. Keep this page open to continue.</p>}{days.map((day, d) => <section key={d} className="space-y-3 rounded-xl border p-4">
    <h2 className="font-semibold">{day.date} · {day.minutes} minutes</h2><p>{day.topics.join(" · ")}</p>
    <ul className="space-y-3">{day.tasks.map((task, t) => <li key={t} className="space-y-1"><label className="flex items-start gap-3"><input type="checkbox" className="mt-1 size-4" checked={checked.includes(`${d}:${t}`)} onChange={() => toggle(`${d}:${t}`)} /><span>{task.text}</span></label><Sources ids={task.chunk_ids} citations={citations} /></li>)}</ul>
  </section>)}</div>;
}

function Quiz({ questions, citations }: { questions: Question[]; citations: Citation[] }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const q = questions[index];
  function next() { if (index === questions.length - 1) setFinished(true); else setIndex(index + 1); setSelected(null); setRevealed(false); }
  if (finished) return <section className="space-y-4" aria-live="polite"><h2 className="text-xl font-medium">Quiz complete</h2><p>{score} of {questions.filter(q => q.type === "mcq").length} multiple-choice answers correct</p><p>Short answers are for your own review.</p><Button onClick={() => { setIndex(0); setScore(0); setFinished(false); }}>Retry quiz</Button></section>;
  return <section className="space-y-4 rounded-xl border p-5" aria-live="polite"><p className="text-sm text-muted-foreground">Question {index + 1} of {questions.length}</p><h2 className="text-lg font-medium">{q.prompt}</h2>
    {q.type === "mcq" ? <div className="grid gap-2">{q.choices!.map((choice, i) => <Button key={i} variant="outline" className="h-auto min-h-11 justify-start whitespace-normal text-left" disabled={revealed} onClick={() => { setSelected(i); setRevealed(true); if (i === q.answer_index) setScore(score + 1); }}>{choice}</Button>)}</div> : !revealed && <Button onClick={() => setRevealed(true)}>Show answer</Button>}
    {revealed && <div className="space-y-3"><p className="font-medium">{q.type === "mcq" ? selected === q.answer_index ? "Correct!" : `Not quite. Correct answer: ${q.choices![q.answer_index!]}` : q.answer_text}</p><p>{q.explanation}</p><Sources ids={q.chunk_ids} citations={citations} /><div><Button onClick={next}>{index === questions.length - 1 ? "See score" : "Next question"}</Button></div></div>}
  </section>;
}

function Flashcards({ cards, citations }: { cards: Card[]; citations: Citation[] }) {
  const [order, setOrder] = useState(() => cards.map((_, i) => i));
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [piles, setPiles] = useState<Record<number, "got" | "again">>({});
  const cardId = order[index];
  const card = cards[cardId];
  function move(delta: number) { setIndex((index + delta + cards.length) % cards.length); setFlipped(false); }
  function mark(pile: "got" | "again") { setPiles({ ...piles, [cardId]: pile }); move(1); }
  function shuffle() {
    const next = [...order];
    for (let i = next.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [next[i], next[j]] = [next[j], next[i]]; }
    setOrder(next); setIndex(0); setFlipped(false);
  }
  return <section className="space-y-4" onKeyDown={e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); move(e.key === "ArrowRight" ? 1 : -1); } }}>
    <p aria-live="polite">Card {index + 1} of {cards.length}</p>
    <button aria-label="Flip card" aria-pressed={flipped} className="min-h-52 w-full rounded-2xl border bg-card p-6 text-lg shadow-sm transition-colors aria-pressed:border-primary/40 aria-pressed:bg-accent focus-visible:outline-2" onClick={() => setFlipped(!flipped)}>{flipped ? card.back : card.front}</button>
    <p className="text-sm text-muted-foreground">Click or press Space to flip. Use the arrow keys to move.</p>
    {flipped && <Sources ids={card.chunk_ids} citations={citations} />}
    <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => move(-1)}>Previous</Button><Button variant="outline" onClick={() => move(1)}>Next</Button><Button variant="outline" onClick={shuffle}>Shuffle</Button></div>
    <div className="flex gap-2"><Button onClick={() => mark("got")}>Got it</Button><Button variant="outline" onClick={() => mark("again")}>Again</Button></div>
    <p role="status">Got it: {Object.values(piles).filter(p => p === "got").length} · Again: {Object.values(piles).filter(p => p === "again").length}</p>
  </section>;
}
