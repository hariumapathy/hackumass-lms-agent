import type { ReactNode } from "react";

/** A screen a later-stage spec fills in (named in each page's comment). Keeps the S30 route table navigable. */
export function Placeholder({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-muted-foreground">Coming soon.</p>
      {children}
    </div>
  );
}
