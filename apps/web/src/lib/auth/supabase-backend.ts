// Supabase Auth (Google + email magic link), session persisted in the browser (S30 rule 2).
import { createClient, type Session } from "@supabase/supabase-js";
import { config } from "@/lib/config";
import type { AuthBackend, AuthSession } from "./backend";

const toSession = (s: Session | null): AuthSession | null =>
  s ? { accessToken: s.access_token, user: { id: s.user.id, email: s.user.email ?? null } } : null;

export function createSupabaseAuthBackend(): AuthBackend {
  const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
  });
  const callbackUrl = () => `${window.location.origin}/auth/callback`;

  return {
    mode: "supabase",
    async getSession() {
      // getSession refreshes an expired access token when a refresh token exists.
      const { data } = await supabase.auth.getSession();
      return toSession(data.session);
    },
    onChange(cb) {
      const { data } = supabase.auth.onAuthStateChange((_event, session) => cb(toSession(session)));
      return () => data.subscription.unsubscribe();
    },
    async signInWithGoogle() {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: callbackUrl() },
      });
      if (error) throw error;
    },
    async signInWithEmail(email) {
      const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: callbackUrl() } });
      if (error) throw error;
    },
    async signIn() {
      throw new Error("Demo sign-in is only available in mock mode.");
    },
    async signOut() {
      await supabase.auth.signOut();
    },
  };
}
