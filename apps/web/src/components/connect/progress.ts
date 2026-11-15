// Onboarding progress (S31 rule 5): connections come from /me; choices the API can't know about
// (welcome seen, optional steps skipped, calendar added/skipped) are kept in localStorage per user.
import type { Me, Platform } from "@/lib/api/types";

export const STEPS = ["welcome", "canvas", "umass", "calendar", "finishing"] as const;
export type Step = (typeof STEPS)[number];

/** Optional live-login platforms on the UMass step. */
export const LOGIN_PLATFORMS = ["gradescope", "piazza"] as const satisfies readonly Platform[];

export interface OnboardingProgress {
  welcomed?: boolean;
  skipped?: Platform[];
  calendar?: "added" | "skipped";
}

const key = (userId: string) => `onboarding:${userId}`;

export function loadProgress(userId: string): OnboardingProgress {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(key(userId)) ?? "{}") as OnboardingProgress;
  } catch {
    return {};
  }
}

export function saveProgress(userId: string, progress: OnboardingProgress) {
  window.localStorage.setItem(key(userId), JSON.stringify(progress));
}

export function isConnected(me: Me, platform: Platform): boolean {
  return me.connections.some((c) => c.platform === platform && c.status === "active");
}

export function firstIncompleteStep(me: Me, progress: OnboardingProgress): Step {
  if (!isConnected(me, "canvas")) return progress.welcomed ? "canvas" : "welcome";
  const skipped = progress.skipped ?? [];
  if (LOGIN_PLATFORMS.some((p) => !isConnected(me, p) && !skipped.includes(p))) return "umass";
  if (!progress.calendar) return "calendar";
  return "finishing";
}
