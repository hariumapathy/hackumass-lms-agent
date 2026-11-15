"use client";

import { useEffect, useState } from "react";
import { Eye, ExternalLink, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { getApiConfig } from "@/lib/api/client";

type State = { kind: "loading" } | { kind: "ready"; url: string } | { kind: "error" };

/** Fetches a stored file with the student's sign-in (an <iframe> can't send it) and returns a
 * same-origin blob URL; the browser's own PDF viewer then opens it at `#page=N`. The dialog
 * mounts this fresh on every open, so it starts in `loading`. */
function useFileUrl(fileId: string): State {
  const [state, setState] = useState<State>({ kind: "loading" });
  useEffect(() => {
    let url: string | null = null;
    const ctrl = new AbortController();
    (async () => {
      try {
        const { baseUrl, getToken } = getApiConfig();
        const token = await getToken();
        const res = await fetch(`${baseUrl}/files/${encodeURIComponent(fileId)}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(String(res.status));
        const blob = await res.blob();
        url = URL.createObjectURL(blob.type ? blob : new Blob([blob], { type: "application/pdf" }));
        setState({ kind: "ready", url });
      } catch {
        if (!ctrl.signal.aborted) setState({ kind: "error" });
      }
    })();
    return () => {
      ctrl.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [fileId]);
  return state;
}

export interface FileViewerProps {
  fileId: string;
  title: string;
  page?: number | null;
  /** The original on the platform (from the API, never built here). */
  sourceUrl: string;
  sourceLabel: string;
}

/** "View" button + dialog with the course file, opened at the cited page. */
export function FileViewerButton(props: FileViewerProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button type="button" size="xs" variant="outline" onClick={() => setOpen(true)} aria-label={`View ${props.title}`}>
        <Eye aria-hidden /> View
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        {open && <FileViewerDialog {...props} />}
      </Dialog>
    </>
  );
}

function FileViewerDialog({ fileId, title, page, sourceUrl, sourceLabel }: FileViewerProps) {
  const state = useFileUrl(fileId);
  const src = state.kind === "ready" ? `${state.url}${page ? `#page=${page}` : ""}` : null;
  return (
    <DialogContent className="flex h-[92dvh] w-[calc(100vw-1rem)] max-w-5xl flex-col gap-3 p-3 sm:max-w-5xl sm:p-4">
      <DialogHeader className="pr-8 text-left">
        <DialogTitle className="truncate text-base">{title}</DialogTitle>
        <DialogDescription className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {page ? <span>Page {page}</span> : null}
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-foreground underline"
          >
            Open in {sourceLabel} <ExternalLink className="size-3" aria-hidden />
          </a>
        </DialogDescription>
      </DialogHeader>
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-md border bg-muted">
        {state.kind === "loading" && (
          <div className="absolute inset-0 grid place-items-center text-sm text-muted-foreground" role="status">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Opening the file…
            </span>
          </div>
        )}
        {state.kind === "error" && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm">
            <p className="max-w-sm text-muted-foreground">
              We couldn&apos;t open this file here. Use &ldquo;Open in {sourceLabel}&rdquo; above to see it there.
            </p>
          </div>
        )}
        {src && <iframe key={src} src={src} title={title} className="size-full border-0 bg-background" />}
      </div>
    </DialogContent>
  );
}
