"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, CalendarCheck, LogOut, MessageSquare, Settings, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/utils";
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
  { href: "/study", label: "Study", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
];

const isActive = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

export function useCourses() {
  return useQuery({ queryKey: ["courses"], queryFn: () => api().courses(), staleTime: 5 * 60_000 });
}

/** App frame: left sidebar on desktop, bottom tab bar under 768px (S30 rule 1). */
export function AppShell({ children }: { children: ReactNode }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  return isDesktop ? (
    <div className="flex min-h-dvh">
      <SyncMonitor />
      <Sidebar />
      <main className="min-w-0 flex-1 px-6 py-8">
        <ExpiryBanner />
        {children}
      </main>
    </div>
  ) : (
    <div className="flex min-h-dvh flex-col">
      <SyncMonitor />
      <main className="min-w-0 flex-1 px-4 pt-6 pb-24">
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
  return (
    <nav aria-label="Sidebar" className="sticky top-0 flex h-dvh w-60 shrink-0 flex-col gap-6 border-r bg-sidebar px-3 py-6">
      <span className="px-3 text-sm font-semibold tracking-tight">LMS Agent</span>
      <ul className="flex flex-col gap-1">
        {NAV.map((item) => (
          <li key={item.href}>
            <NavLink item={item} active={isActive(pathname, item.href)} />
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-1">
        <span className="px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Courses</span>
        <ul className="flex flex-col gap-0.5">
          {(courses.data ?? []).map((c) => (
            <li key={c.id}>
              <Link
                href={`/courses/${c.id}`}
                aria-current={isActive(pathname, `/courses/${c.id}`) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm hover:bg-sidebar-accent focus-visible:outline-2",
                  isActive(pathname, `/courses/${c.id}`) && "bg-sidebar-accent font-medium",
                )}
              >
                <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: c.color ?? "currentColor" }} aria-hidden />
                {c.code}
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <Button variant="ghost" size="sm" className="mt-auto justify-start" onClick={() => void signOut()}>
        <LogOut aria-hidden /> Sign out
      </Button>
    </nav>
  );
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent focus-visible:outline-2",
        active && "bg-sidebar-accent font-medium",
      )}
    >
      <Icon className="size-4" aria-hidden />
      {item.label}
    </Link>
  );
}

function BottomTabs() {
  const pathname = usePathname();
  return (
    <nav aria-label="Bottom tabs" className="fixed inset-x-0 bottom-0 z-10 border-t bg-background pb-[env(safe-area-inset-bottom)]">
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
                  "flex flex-col items-center gap-1 py-2 text-xs text-muted-foreground",
                  active && "font-medium text-foreground",
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
