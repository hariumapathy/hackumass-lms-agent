import type { AuthUser } from "./auth-context";

export interface AuthSession {
  accessToken: string;
  user: AuthUser;
}

/** What AuthProvider needs from an identity provider (Supabase, or the demo stand-in). */
export interface AuthBackend {
  mode: "supabase" | "demo";
  getSession(): Promise<AuthSession | null>;
  onChange(cb: (session: AuthSession | null) => void): () => void;
  signInWithGoogle(): Promise<void>;
  signInWithEmail(email: string): Promise<void>;
  /** Demo backend only: sign in without a provider. */
  signIn(): Promise<void>;
  signOut(): Promise<void>;
}
