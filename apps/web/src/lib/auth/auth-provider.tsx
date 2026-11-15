"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { configureApi } from "@/lib/api/client";
import { supabaseConfigured } from "@/lib/config";
import { AuthContext, type AuthState } from "./auth-context";
import type { AuthBackend, AuthSession } from "./backend";
import { createDemoAuthBackend } from "./demo-backend";
import { createSupabaseAuthBackend } from "./supabase-backend";

function defaultBackend(): AuthBackend {
  return supabaseConfigured() ? createSupabaseAuthBackend() : createDemoAuthBackend();
}

export function AuthProvider({ backend: injected, children }: { backend?: AuthBackend; children: ReactNode }) {
  const router = useRouter();
  const [backend] = useState<AuthBackend>(() => injected ?? defaultBackend());
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  // Wire the API client once, during the first render, before any child effect can call it.
  useState(() => {
    let signingOut = false; // several requests can 401 at once; sign out only once
    configureApi({
      getToken: async () => (await backend.getSession())?.accessToken ?? null,
      onUnauthorized: async () => {
        // S30 rule 2: a 401 means the session is gone (refresh already failed) -> sign out + redirect.
        if (signingOut) return;
        signingOut = true;
        try {
          await backend.signOut();
          setSession(null);
          router.replace("/");
        } finally {
          signingOut = false;
        }
      },
    });
  });

  useEffect(() => {
    let active = true;
    backend.getSession().then((s) => {
      if (!active) return;
      setSession(s);
      setLoading(false);
    });
    const unsubscribe = backend.onChange((s) => {
      setSession(s);
      setLoading(false);
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, [backend]);

  const value = useMemo<AuthState>(
    () => ({
      status: loading ? "loading" : session ? "signed_in" : "signed_out",
      mode: backend.mode,
      user: session?.user ?? null,
      getAccessToken: async () => (await backend.getSession())?.accessToken ?? null,
      signInWithGoogle: () => backend.signInWithGoogle(),
      signInWithEmail: (email) => backend.signInWithEmail(email),
      signInDemo: () => backend.signIn(),
      signOut: async () => {
        await backend.signOut();
        setSession(null);
      },
    }),
    [backend, loading, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
