// Demo sign-in for mock mode (NEXT_PUBLIC_API_MOCKS=1 without Supabase env).
// Lets the UI and e2e tests run with no Supabase project. Never used when Supabase is configured.
import type { AuthBackend, AuthSession } from "./backend";

const KEY = "lms-agent-demo-session";
const DEMO_SESSION: AuthSession = {
  accessToken: "demo-token",
  user: { id: "u0000000-0000-4000-8000-000000000001", email: "demo@example.com" },
};

export function createDemoAuthBackend(): AuthBackend {
  const listeners = new Set<(s: AuthSession | null) => void>();
  const read = (): AuthSession | null => {
    try {
      return window.localStorage.getItem(KEY) ? DEMO_SESSION : null;
    } catch {
      return null;
    }
  };
  const write = (s: AuthSession | null) => {
    try {
      if (s) window.localStorage.setItem(KEY, "1");
      else window.localStorage.removeItem(KEY);
    } catch {
      // storage unavailable: session lasts for this page only
    }
    for (const l of listeners) l(s);
  };

  return {
    mode: "demo",
    getSession: async () => read(),
    onChange(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    signIn: async () => write(DEMO_SESSION),
    signInWithGoogle: async () => write(DEMO_SESSION),
    signInWithEmail: async () => write(DEMO_SESSION),
    signOut: async () => write(null),
  };
}
