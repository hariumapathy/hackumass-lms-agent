import type { Platform } from "@/lib/api/types";

export const PLATFORM_LABEL: Record<Platform, string> = {
  canvas: "Canvas",
  gradescope: "Gradescope",
  echo360: "Echo360",
  piazza: "Piazza",
};

/** Platforms a student can actually connect. Echo360 has no connector yet (S15 is stretch), so it is never offered. */
export const CONNECTABLE_PLATFORMS = ["canvas", "gradescope", "piazza"] as const satisfies readonly Platform[];

export const isConnectable = (p: Platform): boolean => (CONNECTABLE_PLATFORMS as readonly Platform[]).includes(p);

/** What the login window asks for, in plain words (shown while the live login is open). */
export const LOGIN_HINT: Partial<Record<Platform, string>> = {
  gradescope: "Log in with your NetID and approve Duo.",
  piazza: "Log in to Piazza the way you normally do.",
};
