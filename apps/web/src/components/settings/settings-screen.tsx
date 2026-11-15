"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, RefreshCw } from "lucide-react";
import { calendarLinks } from "@/components/connect/calendar-links";
import { ErrorState, Loading } from "@/components/states/states";
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
import { api, ApiError } from "@/lib/api/client";
import type { Connection, Me, Platform } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-context";
import { PLATFORM_LABEL } from "@/lib/platforms";
import { shortAgo } from "@/lib/time";

const PLATFORMS: Platform[] = ["canvas", "gradescope", "echo360"];
const DAY = 86_400_000;

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Try again.");

/** Settings (S34): connections, profile, calendar, privacy; AI choice tucked under Advanced. */
export function SettingsScreen() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api().me() });
  if (me.isPending) return <Loading label="Loading settings…" rows={4} />;
  if (me.isError) return <ErrorState error={me.error} onRetry={() => void me.refetch()} />;
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <ConnectionsSection me={me.data} />
      <ProfileSection me={me.data} />
      <CalendarSection />
      <PrivacySection />
      <AdvancedSection me={me.data} />
    </div>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div>
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Confirm dialog that names exactly what will happen (S34 rule 3). */
function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  busy,
  confirmDisabled,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  busy?: boolean;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button variant={destructive ? "destructive" : "default"} disabled={busy || confirmDisabled} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---- Connections ----

function statusText(c: Connection | undefined): string {
  if (!c || c.status === "disconnected") return "Not connected";
  if (c.status === "needs_reconnect") return "Needs reconnecting";
  if (c.status === "error") return "Having trouble";
  return "Connected";
}

function ConnectionsSection({ me }: { me: Me }) {
  return (
    <Section title="Your accounts" description="We keep your classes up to date from these.">
      <ul className="flex flex-col gap-3">
        {PLATFORMS.map((p) => (
          <ConnectionRow key={p} platform={p} connection={me.connections.find((c) => c.platform === p)} />
        ))}
      </ul>
    </Section>
  );
}

function ConnectionRow({ platform, connection }: { platform: Platform; connection?: Connection }) {
  const qc = useQueryClient();
  const nameId = useId();
  const label = PLATFORM_LABEL[platform];
  const [confirming, setConfirming] = useState(false);
  const [now] = useState(() => Date.now());
  const connected = Boolean(connection && connection.status !== "disconnected");
  const healthy = connection?.status === "active";

  const disconnect = useMutation({
    mutationFn: () => api().disconnect(platform),
    onSuccess: async () => {
      setConfirming(false);
      await Promise.all(["me", "today", "courses"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
    },
  });
  const refresh = useMutation({
    mutationFn: () => api().sync({ platform }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["today"] }),
  });

  let expiry: string | null = null;
  if (platform === "canvas" && connection?.expires_at) {
    const days = Math.floor((new Date(connection.expires_at).getTime() - now) / DAY);
    expiry = days <= 0 ? "Access has ended" : `Access ends in ${days} ${days === 1 ? "day" : "days"}`;
  }

  return (
    <li aria-labelledby={nameId} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-0.5">
        <span id={nameId} className="font-medium">
          {label}
        </span>
        <span className="text-sm">{statusText(connection)}</span>
        <span className="text-xs text-muted-foreground">
          {connected && connection?.last_sync_at ? `Updated ${shortAgo(connection.last_sync_at)} ago` : null}
          {connected && connection?.last_sync_at && expiry ? " · " : null}
          {expiry}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {healthy ? (
          <Button variant="outline" size="sm" disabled={refresh.isPending} onClick={() => refresh.mutate()} aria-label={`Refresh ${label}`}>
            {refresh.isSuccess ? <Check aria-hidden /> : <RefreshCw aria-hidden />} {refresh.isSuccess ? "Updating" : "Refresh"}
          </Button>
        ) : (
          <Button asChild size="sm">
            <Link href={`/onboarding?reconnect=${platform}`}>{connected ? `Reconnect ${label}` : `Connect ${label}`}</Link>
          </Button>
        )}
        {connected && (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)} aria-label={`Disconnect ${label}`}>
            Disconnect
          </Button>
        )}
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Disconnect ${label}?`}
        description={`We'll stop updating ${label} and forget its login. Your other classes stay. You can connect it again any time.`}
        confirmLabel="Disconnect"
        destructive
        busy={disconnect.isPending}
        onConfirm={() => disconnect.mutate()}
      >
        {disconnect.isError && <p role="alert" className="text-sm text-destructive">{errorText(disconnect.error)}</p>}
      </ConfirmDialog>
    </li>
  );
}

// ---- Profile ----

const browserTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return "America/New_York";
  }
};

function ProfileSection({ me }: { me: Me }) {
  const qc = useQueryClient();
  const [name, setName] = useState(me.display_name ?? "");
  const [tz, setTz] = useState(me.timezone || browserTimeZone());
  const zones = (() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return [tz];
    }
  })();
  const save = useMutation({
    mutationFn: () => api().patchMe({ display_name: name.trim() || null, timezone: tz }),
    onSuccess: (updated) => qc.setQueryData(["me"], updated),
  });

  return (
    <Section title="Profile">
      <form
        className="flex flex-col gap-3 sm:max-w-md"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label className="flex flex-col gap-1 text-sm">
          Your name
          <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Time zone
          <select
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            className="h-9 rounded-md border bg-transparent px-3 text-sm shadow-xs focus-visible:outline-2"
          >
            {(zones.includes(tz) ? zones : [tz, ...zones]).map((z) => (
              <option key={z} value={z}>
                {z.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="outline" disabled={save.isPending}>
            Save
          </Button>
          {save.isSuccess && <span role="status" className="text-sm text-green-700 dark:text-green-400">Saved</span>}
          {save.isError && <span role="alert" className="text-sm text-destructive">{errorText(save.error)}</span>}
        </div>
      </form>
    </Section>
  );
}

// ---- Calendar ----

/** Show where the link points without exposing the private part in full. */
function maskFeedUrl(url: string): string {
  try {
    const u = new URL(url);
    const last = u.pathname.split("/").pop() ?? "";
    return `${u.host}/…/${last.length > 18 ? `…${last.slice(-18)}` : last}`;
  } catch {
    return "Private calendar link";
  }
}

function CalendarSection() {
  const qc = useQueryClient();
  const feed = useQuery({ queryKey: ["calendar-feed"], queryFn: () => api().calendarFeed() });
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);
  const rotate = useMutation({
    mutationFn: () => api().rotateCalendarFeed(),
    onSuccess: (data) => {
      qc.setQueryData(["calendar-feed"], data);
      setConfirming(false);
    },
  });

  return (
    <Section
      title="Calendar"
      description="Your deadlines and study sessions, in the calendar app you already use. Calendar apps refresh on their own schedule (Google can take a few hours)."
    >
      {feed.isPending && <Loading rows={1} />}
      {feed.isError && <ErrorState error={feed.error} onRetry={() => void feed.refetch()} />}
      {feed.data && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <a href={calendarLinks(feed.data.url).google} target="_blank" rel="noopener noreferrer">
                Add to Google Calendar
              </a>
            </Button>
            <Button asChild size="sm" variant="outline">
              <a href={calendarLinks(feed.data.url).apple}>Add to Apple Calendar</a>
            </Button>
            <Button asChild size="sm" variant="outline">
              <a href={calendarLinks(feed.data.url).outlook} target="_blank" rel="noopener noreferrer">
                Add to Outlook
              </a>
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono text-xs">{maskFeedUrl(feed.data.url)}</span>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                void navigator.clipboard?.writeText(feed.data.url).then(() => setCopied(true));
              }}
            >
              {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? "Copied" : "Copy link"}
            </Button>
            <Button variant="ghost" size="xs" onClick={() => setConfirming(true)}>
              Get a new link
            </Button>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Get a new private calendar link?"
        description="Your old link stops working right away. Calendars using it stop updating until you add the new one."
        confirmLabel="Get new link"
        busy={rotate.isPending}
        onConfirm={() => rotate.mutate()}
      >
        {rotate.isError && <p role="alert" className="text-sm text-destructive">{errorText(rotate.error)}</p>}
      </ConfirmDialog>
    </Section>
  );
}

// ---- Privacy ----

function PrivacySection() {
  const { signOut } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const del = useMutation({
    mutationFn: () => api().deleteMyData(),
    onSuccess: async () => {
      await signOut();
      router.replace("/");
    },
  });

  return (
    <Section title="Privacy">
      <ul className="list-disc pl-5 text-sm text-muted-foreground">
        <li>We keep a copy of your classes, deadlines, course files and chats so answers are fast and cite the source.</li>
        <li>We never see or keep your UMass, Canvas or Gradescope passwords.</li>
        <li>Your questions go to the AI service chosen under Advanced (Gemini by default).</li>
      </ul>
      <Button
        variant="destructive"
        className="w-fit"
        onClick={() => {
          setTyped("");
          setOpen(true);
        }}
      >
        Delete my data
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete all your data?"
        description="This deletes your classes, files, chats and account connections from our servers, then signs you out. It can't be undone."
        confirmLabel="Delete everything"
        destructive
        busy={del.isPending}
        confirmDisabled={typed !== "DELETE"}
        onConfirm={() => del.mutate()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Type DELETE to confirm
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        </label>
        {del.isError && <p role="alert" className="text-sm text-destructive">{errorText(del.error)}</p>}
      </ConfirmDialog>
    </Section>
  );
}

// ---- Advanced: AI choice ----

function AdvancedSection({ me }: { me: Me }) {
  const qc = useQueryClient();
  const models = useQuery({ queryKey: ["models"], queryFn: () => api().models(), staleTime: 5 * 60_000 });
  const choose = useMutation({
    mutationFn: (id: string) => api().patchMe({ model_choice: id }),
    onSuccess: (updated) => qc.setQueryData(["me"], updated),
  });
  const current = me.model_choice ?? models.data?.default;

  const group = (tier: "recommended" | "experimental", title: string) => {
    const options = (models.data?.models ?? []).filter((m) => m.tier === tier);
    if (options.length === 0) return null;
    return (
      <div role="radiogroup" aria-label={title} className="flex flex-col gap-2">
        <span className="text-sm font-medium">{title}</span>
        {options.map((m) => (
          <label key={m.id} className={`flex items-center gap-2 text-sm ${m.available ? "" : "text-muted-foreground"}`}>
            <input
              type="radio"
              name="ai-choice"
              value={m.id}
              checked={current === m.id}
              disabled={!m.available || choose.isPending}
              onChange={() => choose.mutate(m.id)}
            />
            {m.label}
            {m.id === models.data?.default && " (default)"}
            {!m.available && " (not available right now)"}
          </label>
        ))}
      </div>
    );
  };

  return (
    <details className="rounded-lg border p-4">
      <summary className="cursor-pointer select-none font-medium">Advanced</summary>
      <div className="flex flex-col gap-4 pt-4">
        <p className="text-sm text-muted-foreground">Which AI answers your questions. The default works well for most students.</p>
        {models.isPending && <Loading rows={2} />}
        {models.isError && <ErrorState error={models.error} onRetry={() => void models.refetch()} />}
        {group("recommended", "Recommended")}
        {group("experimental", "Experimental")}
        {models.data?.models.some((m) => m.tier === "experimental") && (
          <p className="text-xs text-muted-foreground">Experimental options may skip tools or make mistakes.</p>
        )}
        {choose.isSuccess && <span role="status" className="text-sm text-green-700 dark:text-green-400">Saved</span>}
        {choose.isError && <span role="alert" className="text-sm text-destructive">{errorText(choose.error)}</span>}
      </div>
    </details>
  );
}
