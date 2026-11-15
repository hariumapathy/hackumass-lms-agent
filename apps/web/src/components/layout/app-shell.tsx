"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, Layers, LogOut, MessageSquare, Settings, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { CourseSummary } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/auth-context";
import { splitCourses } from "@/lib/courses";
import { cn } from "@/lib/utils";
import { BrandMark } from "./brand-mark";
import { ExpiryBanner } from "./expiry-banner";
import { SyncMonitor } from "./sync-monitor";
import { DESKTOP_QUERY, useMediaQuery } from "./use-media-query";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: "/today", label: "Today", icon: CalendarCheck },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/sessions", label: "Sessions", icon: Layers },
  { href: "/settings", label: "Settings", icon: Settings },
];

const isActive = (pathname: string, href: string) =>
  pathname === href || pathname.startsWith(`${href}/`) || (href === "/sessions" && pathname.startsWith("/study"));

export function useCourses() {
  return useQuery({ queryKey: ["courses"], queryFn: () => api().courses(), staleTime: 5 * 60_000 });
}

/** App frame: left sidebar on desktop, top bar + bottom tab bar under 768px (S30 rule 1, S35). */
export function AppShell({ children }: { children: ReactNode }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  return isDesktop ? (
    <div className="flex min-h-dvh">
      <SyncMonitor />
      <Sidebar />
      <main className="min-w-0 flex-1 px-8 py-8">
        <ExpiryBanner />
        {children}
      </main>
    </div>
  ) : (
    <div className="flex min-h-dvh flex-col">
      <SyncMonitor />
      <header className="sticky top-0 z-20 flex items-center gap-2 bg-maroon px-4 py-2.5 text-white shadow-sm">
        <BrandMark size="sm" />
      </header>
      <main className="min-w-0 flex-1 px-4 pt-5 pb-24">
        <ExpiryBanner />
        {children}
      </main>
      <BottomTabs />
    </div>
  );
}

function Sidebar() {
  const pathname = usePathname();
  const { signOut } = useAuth();
  const courses = useCourses();
  const split = splitCourses(courses.data ?? []);
  return (
    <nav
      aria-label="Sidebar"
      className="sticky top-0 flex h-dvh w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar"
    >
      <div className="bg-maroon px-5 py-5 text-white">
        <BrandMark />
      </div>
      <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-5">
        <ul className="flex flex-col gap-1">
          {NAV.map((item) => (
            <li key={item.href}>
              <NavLink item={item} active={isActive(pathname, item.href)} />
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-1.5">
          <span className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Your courses
          </span>
          <CourseLinks courses={split.active} pathname={pathname} />
          {split.other.length > 0 && (
            <details className="group" open={split.other.some((c) => isActive(pathname, `/courses/${c.id}`))}>
              <summary className="cursor-pointer list-none rounded-lg px-3 py-1.5 text-xs text-muted-foreground select-none hover:bg-sidebar-accent">
                <span className="group-open:hidden">Show</span>
                <span className="hidden group-open:inline">Hide</span> other courses ({split.other.length})
              </summary>
              <CourseLinks courses={split.other} pathname={pathname} />
            </details>
          )}
        </div>
      </div>
      <div className="border-t border-sidebar-border p-3">
        <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground" onClick={() => void signOut()}>
          <LogOut aria-hidden /> Sign out
        </Button>
      </div>
    </nav>
  );
}

function CourseLinks({ courses, pathname }: { courses: CourseSummary[]; pathname: string }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {courses.map((c) => {
        const active = isActive(pathname, `/courses/${c.id}`);
        return (
          <li key={c.id}>
            <Link
              href={`/courses/${c.id}`}
              aria-current={active ? "page" : undefined}
              title={c.name}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm text-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-foreground focus-visible:outline-2",
                active && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
              )}
            >
              <span
                className="size-2.5 shrink-0 rounded-full ring-2 ring-white/70 dark:ring-black/40"
                style={{ backgroundColor: c.color ?? "currentColor" }}
                aria-hidden
              />
              <span className="truncate">{c.code}</span>
              {c.upcoming_count > 0 && (
                <span className="ml-auto rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
                  {c.upcoming_count}
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-foreground focus-visible:outline-2",
        active &&
          "bg-sidebar-accent text-sidebar-accent-foreground before:absolute before:inset-y-1.5 before:left-0 before:w-1 before:rounded-full before:bg-primary",
      )}
    >
      <Icon className={cn("size-4", active ? "text-primary" : "text-muted-foreground")} aria-hidden />
      {item.label}
    </Link>
  );
}

function BottomTabs() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Bottom tabs"
      className="fixed inset-x-0 bottom-0 z-20 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    >
      <ul className="grid grid-cols-4">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex flex-col items-center gap-1 py-2.5 text-xs text-muted-foreground transition-colors",
                  active && "font-semibold text-primary before:absolute before:top-0 before:h-0.5 before:w-10 before:rounded-full before:bg-primary",
                )}
              >
                <Icon className="size-5" aria-hidden />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
