"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DropdownMenu } from "radix-ui";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { STUDY_ICONS, STUDY_LABELS } from "@/components/study/study-set-card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import type { ConversationSummary } from "@/lib/api/types";
import { relative } from "@/lib/time";
import { cn } from "@/lib/utils";

export const DELETE_CHAT_TEXT = "Delete this chat? Its flashcards and quizzes stay in Sessions.";

/** Rename + delete a conversation (S36). Keeps the cached lists in step. */
function useSessionMutations(id: string) {
  const qc = useQueryClient();
  const rename = useMutation({
    mutationFn: (title: string) => api().renameConversation(id, title),
    onSuccess: (renamed) => {
      qc.setQueryData<ConversationSummary[]>(["conversations"], (list) =>
        list?.map((c) => (c.id === id ? { ...c, title: renamed.title } : c)),
      );
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      void qc.invalidateQueries({ queryKey: ["conversation", id] });
    },
  });
  const remove = useMutation({
    mutationFn: () => api().deleteConversation(id),
    onSuccess: () => {
      qc.setQueryData<ConversationSummary[]>(["conversations"], (list) => list?.filter((c) => c.id !== id));
      qc.removeQueries({ queryKey: ["conversation", id] });
      void qc.invalidateQueries({ queryKey: ["conversations"] });
      void qc.invalidateQueries({ queryKey: ["study-sets"] });
    },
  });
  return { rename, remove };
}

interface SessionRowProps {
  conversation: ConversationSummary;
  /** compact = the chat page's side list; full = the Sessions page card with study-set chips. */
  variant?: "compact" | "full";
  active?: boolean;
  onDeleted?: () => void;
}

/** One chat in a list: title link, "..." menu with Rename (inline) and Delete (confirm). */
export function SessionRow({ conversation: c, variant = "full", active = false, onDeleted }: SessionRowProps) {
  const { rename, remove } = useSessionMutations(c.id);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const menuButton = useRef<HTMLButtonElement | null>(null);
  const skipFocusReturn = useRef(false);
  const renameInput = useRef<HTMLInputElement | null>(null);
  const sets = c.study_sets ?? [];
  const full = variant === "full";

  async function save(title: string) {
    setEditing(false);
    const next = title.trim();
    if (!next || next === c.title) return;
    rename.mutate(next);
  }

  async function confirmDelete() {
    try {
      await remove.mutateAsync();
      setConfirming(false);
      onDeleted?.();
    } catch {
      /* the dialog shows the error */
    }
  }

  return (
    <li
      aria-label={c.title}
      className={cn(
        "group relative",
        full
          ? "rounded-xl border bg-card p-4 shadow-xs transition-colors focus-within:border-primary/40 hover:border-primary/30"
          : "rounded-lg",
        !full && active && "bg-accent",
      )}
    >
      <div className={cn("flex items-center gap-1", full && "items-start gap-3")}>
        <div className="min-w-0 flex-1">
          {editing ? (
            <RenameField
              inputRef={renameInput}
              initial={c.title}
              onSave={save}
              onCancel={() => {
                setEditing(false);
                menuButton.current?.focus();
              }}
              compact={!full}
            />
          ) : (
            <Link
              href={`/chat/${encodeURIComponent(c.id)}`}
              aria-current={active ? "page" : undefined}
              className={cn(
                "block truncate rounded-md focus-visible:outline-2 focus-visible:outline-offset-2",
                full
                  ? "font-display text-lg font-semibold hover:text-primary"
                  : "px-3 py-1.5 text-sm text-foreground/80 hover:text-foreground",
                !full && active && "font-medium text-accent-foreground",
              )}
            >
              {c.title}
            </Link>
          )}
          {full && <p className="mt-0.5 text-xs text-muted-foreground">Updated {relative(c.updated_at)}</p>}
          {rename.isError && (
            <p role="alert" className={cn("text-xs text-destructive", !full && "px-3")}>
              Couldn&apos;t rename this chat. Try again.
            </p>
          )}
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <Button
              ref={menuButton}
              variant="ghost"
              size="icon"
              aria-label={`Options for ${c.title}`}
              className={cn(
                "size-8 shrink-0 text-muted-foreground",
                !full && "opacity-70 group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100",
              )}
            >
              <MoreHorizontal aria-hidden />
            </Button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className="z-50 min-w-36 rounded-lg border bg-popover p-1 text-sm text-popover-foreground shadow-md"
              onCloseAutoFocus={(e) => {
                // Rename: the menu's focus trap is gone now, so move focus into the new title field.
                if (skipFocusReturn.current) {
                  e.preventDefault();
                  skipFocusReturn.current = false;
                  renameInput.current?.focus();
                  renameInput.current?.select();
                }
              }}
            >
              <DropdownMenu.Item
                className="flex cursor-default items-center gap-2 rounded-md px-2.5 py-1.5 outline-none select-none data-[highlighted]:bg-accent"
                onSelect={() => {
                  skipFocusReturn.current = true;
                  setEditing(true);
                }}
              >
                <Pencil className="size-4" aria-hidden /> Rename
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className="flex cursor-default items-center gap-2 rounded-md px-2.5 py-1.5 text-destructive outline-none select-none data-[highlighted]:bg-destructive/10"
                onSelect={() => {
                  remove.reset();
                  setConfirming(true);
                }}
              >
                <Trash2 className="size-4" aria-hidden /> Delete
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>

      {full && sets.length > 0 && (
        <ul aria-label="Made in this chat" className="mt-3 flex flex-wrap gap-2">
          {sets.map((st) => {
            const Icon = STUDY_ICONS[st.type];
            return (
              <li key={st.id} className="min-w-0 max-w-full">
                <Link
                  href={`/study/${encodeURIComponent(st.id)}`}
                  title={st.title}
                  className="flex min-w-0 items-center gap-1.5 rounded-full border border-primary/25 bg-accent/60 px-3 py-1 text-xs text-accent-foreground transition-colors hover:border-primary/50 hover:bg-accent focus-visible:outline-2"
                >
                  <Icon className="size-3.5 shrink-0 text-primary" aria-hidden />
                  <span className="shrink-0 font-semibold">{STUDY_LABELS[st.type]}</span>
                  <span className="truncate text-muted-foreground">· {st.title}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent
          onCloseAutoFocus={(e) => {
            // Back to the "..." button when it still exists (cancel); the row is gone after a delete.
            if (menuButton.current?.isConnected) {
              e.preventDefault();
              menuButton.current.focus();
            }
          }}
        >
          <DialogHeader>
            <DialogTitle>Delete &ldquo;{c.title}&rdquo;?</DialogTitle>
            <DialogDescription>{DELETE_CHAT_TEXT}</DialogDescription>
          </DialogHeader>
          {remove.isError && (
            <p role="alert" className="text-sm text-destructive">
              Couldn&apos;t delete this chat. Try again.
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Keep it</Button>
            </DialogClose>
            <Button variant="destructive" disabled={remove.isPending} onClick={() => void confirmDelete()}>
              {remove.isPending ? "Deleting…" : "Delete chat"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  );
}

function RenameField({
  inputRef,
  initial,
  onSave,
  onCancel,
  compact,
}: {
  inputRef: RefObject<HTMLInputElement | null>;
  initial: string;
  onSave: (title: string) => void;
  onCancel: () => void;
  compact: boolean;
}) {
  const [value, setValue] = useState(initial);
  const done = useRef(false);
  // Blur saves only after the field really had focus (the menu's focus trap can bounce it once).
  const focused = useRef(false);
  const finish = (save: boolean) => {
    if (done.current) return;
    done.current = true;
    if (save) onSave(value);
    else onCancel();
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      finish(true);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      finish(false);
    }
  };
  return (
    <Input
      ref={inputRef}
      aria-label="Chat title"
      value={value}
      maxLength={80}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={onKeyDown}
      onFocus={() => (focused.current = true)}
      onBlur={() => focused.current && finish(true)}
      className={cn(compact ? "h-8 text-sm" : "h-9 font-display text-lg font-semibold")}
    />
  );
}
