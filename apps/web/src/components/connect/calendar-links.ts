// "Add to calendar" links built from the feed URL returned by GET /calendar/feed (S31 rule 8, S25).
export interface CalendarLinks {
  google: string;
  apple: string;
  outlook: string;
}

export function canSubscribeRemotely(feedUrl: string): boolean {
  try {
    const { protocol, hostname } = new URL(feedUrl);
    return protocol === "https:" && !/^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1\]?)/i.test(hostname) && !hostname.endsWith(".local");
  } catch {
    return false;
  }
}

export function calendarLinks(feedUrl: string): CalendarLinks {
  const webcal = feedUrl.replace(/^https?:\/\//i, "webcal://");
  return {
    google: `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcal)}`,
    apple: webcal,
    outlook: `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(feedUrl)}&name=${encodeURIComponent("Class deadlines")}`,
  };
}
