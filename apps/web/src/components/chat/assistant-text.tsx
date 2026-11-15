"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Citation } from "@/lib/api/types";
import { CitationCard } from "./citation-card";

const MARKER = / ?\[cite:chunk_(\d+)\]/g;
/** A marker cut off at the end of the streamed text so far, e.g. "[cite:chu" (S02 P4). */
const PARTIAL_MARKER = /\[(?:c(?:i(?:t(?:e(?::(?:c(?:h(?:u(?:n(?:k(?:_\d*)?)?)?)?)?)?)?)?)?)?)?$/;

/**
 * Rewrites [cite:chunk_N] markers into markdown links with private schemes the renderer turns into chips:
 * - citations known: valid IDs -> numbered chip, others dropped (S33 rule 4)
 * - still streaming: placeholder dot (S33 rule 3)
 * - finished without citations (error): markers removed (S33 edge case)
 */
export function prepareMarkdown(text: string, citations: Citation[] | null, streaming: boolean): string {
  const src = streaming ? text.replace(PARTIAL_MARKER, "") : text;
  const numbers = new Map((citations ?? []).map((c, i) => [c.chunk_id, i + 1]));
  return src.replace(MARKER, (match, id: string) => {
    const space = match.startsWith(" ") ? " " : "";
    if (citations) {
      const n = numbers.get(Number(id));
      return n ? `${space}[${n}](cite:${id})` : "";
    }
    return streaming ? `${space}[·](cite-pending:${id})` : "";
  });
}

function CitationChip({ citation, n }: { citation: Citation; n: number }) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label={`Citation ${n}: ${citation.title}`}
        className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md border bg-muted px-1 align-text-top text-xs font-medium hover:bg-accent focus-visible:outline-2"
      >
        {n}
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <CitationCard citation={citation} />
      </PopoverContent>
    </Popover>
  );
}

export function AssistantText({
  text,
  citations,
  streaming,
}: {
  text: string;
  citations: Citation[] | null;
  streaming: boolean;
}) {
  const byId = useMemo(() => new Map((citations ?? []).map((c, i) => [c.chunk_id, { c, n: i + 1 }])), [citations]);
  return (
    <CitationsContext.Provider value={byId}>
      <div className="leading-relaxed">
        <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS} urlTransform={urlTransform}>
          {prepareMarkdown(text, citations, streaming)}
        </ReactMarkdown>
      </div>
    </CitationsContext.Provider>
  );
}

// Module-level (stable) renderer config: if these were recreated per render, every streamed delta
// would remount the DOM, losing focus and closing any open citation card.
const CitationsContext = createContext<Map<number, { c: Citation; n: number }>>(new Map());

function MarkdownLink({ href, children }: { href?: string; children?: ReactNode }) {
  const byId = useContext(CitationsContext);
  if (href?.startsWith("cite:")) {
    const hit = byId.get(Number(href.slice(5)));
    return hit ? <CitationChip citation={hit.c} n={hit.n} /> : null;
  }
  if (href?.startsWith("cite-pending:")) {
    return <span aria-label="Citation pending" className="mx-0.5 inline-block size-1.5 rounded-full bg-muted-foreground/60 align-middle" />;
  }
  // The model never writes links (docs/04): any URL in its text is shown as plain text.
  return <span>{children}</span>;
}

const COMPONENTS: Components = {
  a: MarkdownLink,
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
  code: ({ children }) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{children}</code>,
};

const REMARK_PLUGINS = [remarkGfm];

const urlTransform = (url: string) =>
  url.startsWith("cite:") || url.startsWith("cite-pending:") ? url : defaultUrlTransform(url);
