"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CalendarPlus, CheckCircle2 } from "lucide-react";
import { ErrorState, Loading } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { calendarLinks, canSubscribeRemotely } from "./calendar-links";

export function useCalendarFeed() {
  return useQuery({ queryKey: ["calendar-feed"], queryFn: () => api().calendarFeed(), staleTime: Infinity });
}

/** Google / Apple / Outlook buttons for a feed URL. The raw URL is never shown (S31 rule 8). */
export function CalendarButtons({ feedUrl, onAdded }: { feedUrl: string; onAdded?: () => void }) {
  const links = calendarLinks(feedUrl);
  if (!canSubscribeRemotely(feedUrl)) return (
    <div className="flex flex-col gap-3">
      <Button asChild size="lg" className="w-fit"><a href={feedUrl} download="class-calendar.ics">Download calendar</a></Button>
      <p className="text-sm text-muted-foreground">This demo runs on your laptop. Download the file, then import it into Google Calendar under Settings → Import &amp; export. Download it again after changes.</p>
    </div>
  );
  return (
    <div className="flex flex-col gap-3">
      <Button asChild size="lg" className="w-fit">
        <a href={links.google} target="_blank" rel="noopener noreferrer" onClick={onAdded}>
          <CalendarPlus aria-hidden /> Add to Google Calendar
        </a>
      </Button>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <span className="text-muted-foreground">Use something else?</span>
        <a className="underline" href={links.apple} onClick={onAdded}>
          Apple Calendar
        </a>
        <a className="underline" href={links.outlook} target="_blank" rel="noopener noreferrer" onClick={onAdded}>
          Outlook
        </a>
      </p>
      <p className="text-sm text-muted-foreground">
        New study sessions can take a few hours to show up in Google Calendar.
      </p>
    </div>
  );
}

/** S31 step 4: subscribe to the calendar feed (optional). */
export function CalendarStep({ onDone }: { onDone: (result: "added" | "skipped") => void }) {
  const feed = useCalendarFeed();
  const [added, setAdded] = useState(false);

  return (
    <section aria-labelledby="calendar-step-heading" className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="calendar-step-heading" className="text-2xl font-semibold tracking-tight">
          Add your deadlines to your calendar
        </h1>
        <p className="text-muted-foreground">
          Bring your deadlines and approved study sessions into the calendar app you already use.
        </p>
      </div>

      {feed.isPending ? (
        <Loading label="Getting your calendar link…" rows={1} />
      ) : feed.isError ? (
        <ErrorState error={feed.error} onRetry={() => void feed.refetch()} />
      ) : (
        <CalendarButtons feedUrl={feed.data.url} onAdded={() => setAdded(true)} />
      )}

      <div aria-live="polite" className="flex flex-wrap items-center gap-3">
        {added ? (
          <>
            <span className="inline-flex items-center gap-2 font-medium text-green-700 dark:text-green-400">
              <CheckCircle2 className="size-4" aria-hidden /> Added
            </span>
            <Button onClick={() => onDone("added")}>Continue</Button>
          </>
        ) : (
          <Button variant="ghost" onClick={() => onDone("skipped")}>
            Skip
          </Button>
        )}
      </div>
    </section>
  );
}
