import { ExternalLink } from "lucide-react";
import { FileViewerButton } from "@/components/files/file-viewer";
import { Badge } from "@/components/ui/badge";
import type { Citation } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { relative } from "@/lib/time";

export function formatTimestamp(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

function anchor(c: Citation): string | null {
  if (c.page != null) return `p. ${c.page}`;
  if (c.start_s != null) return c.end_s != null ? `${formatTimestamp(c.start_s)}–${formatTimestamp(c.end_s)}` : formatTimestamp(c.start_s);
  return null;
}

function statusNote(c: Citation): string | null {
  switch (c.status) {
    case "changed":
      return "Changed since this answer";
    case "removed":
      return `Removed from ${PLATFORM_LABEL[c.platform]}`;
    case "locked":
      return "Currently locked";
    default:
      return null;
  }
}

/** What a citation chip opens (S33 rule 4). Links come only from the API (`deep_link`), never built here. */
export function CitationCard({ citation: c }: { citation: Citation }) {
  const where = anchor(c);
  const note = statusNote(c);
  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">{c.title}</span>
        <span className="text-xs text-muted-foreground">
          {c.course_code} · {PLATFORM_LABEL[c.platform]}
          {where && ` · ${where}`}
        </span>
      </div>
      {note && (
        <Badge variant="outline" className="self-start border-amber-500/60 text-amber-700 dark:text-amber-400">
          {note}
        </Badge>
      )}
      <blockquote className="border-l-2 pl-3 text-muted-foreground italic">{c.quote}</blockquote>
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>Synced {relative(c.last_synced_at)}</span>
        <span className="flex items-center gap-2">
        {c.file_id && (
          <FileViewerButton
            fileId={c.file_id}
            title={c.title}
            page={c.page}
            sourceUrl={c.deep_link}
            sourceLabel={PLATFORM_LABEL[c.platform]}
          />
        )}
        <a
          href={c.deep_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-medium text-foreground underline"
        >
          Open source <ExternalLink className="size-3" aria-hidden />
        </a>
        </span>
      </div>
    </div>
  );
}
