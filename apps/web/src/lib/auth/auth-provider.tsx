"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { configureApi } from "@/lib/api/client";
import { makeQueryClient } from "@/lib/api/query-client";
import { invalidateSessionRequests } from "@/lib/api/session-boundary";
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
  const [boundary, setBoundary] = useState(() => ({ session: null as AuthSession | null, client: makeQueryClient(), version: 0 }));
  const latest = useRef(boundary);
  const revision = useRef(0);
  const logout = useRef<Promise<void> | null>(null);
  const [loading, setLoading] = useState(true);

  const transition = useCallback((session: AuthSession | null) => {
    revision.current += 1;
    const previous = latest.current;
    const changed = (previous.session?.user.id ?? null) !== (session?.user.id ?? null);
    if (changed) {
      // Invalidate before exposing the next identity, including non-query SSE work.
      invalidateSessionRequests();
      void previous.client.cancelQueries();
      previous.client.clear();
    }
    const next = {
      session,
      client: changed ? makeQueryClient() : previous.client,
      version: previous.version + (changed ? 1 : 0),
    };
    latest.current = next;
    setBoundary(next);
    setLoading(false);
  }, []);

  const signOut = useCallback(() => {
    if (logout.current) return logout.current;
    transition(null);
    const operation = Promise.resolve().then(() => backend.signOut()).finally(() => {
      logout.current = null;
    });
    logout.current = operation;
    return operation;
  }, [backend, transition]);

  const getToken = useCallback(async () => {
    const owner = latest.current.session?.user.id;
    const version = latest.current.version;
    const fresh = await backend.getSession();
    if (!owner || fresh?.user.id !== owner || latest.current.session?.user.id !== owner || latest.current.version !== version) return null;
    return fresh.accessToken;
  }, [backend]);

  // Configure before passive query effects; callbacks read the latest identity.
  useLayoutEffect(() => {
    let signingOut = false;
    configureApi({
      getToken,
      onUnauthorized: async () => {
        if (signingOut) return;
        signingOut = true;
        try {
          await signOut();
          if (!latest.current.session) router.replace("/");
        } finally {
          signingOut = false;
        }
      },
    });
  }, [getToken, router, signOut]);

  useEffect(() => {
    let active = true;
    let events = 0;
    const initialRevision = revision.current;
    backend.getSession().then((session) => {
      if (active && events === 0 && revision.current === initialRevision && !logout.current) transition(session);
    }).catch(() => {
      if (active && events === 0) transition(null);
    });
    const unsubscribe = backend.onChange((session) => {
      events += 1;
      if (session && logout.current) return; // token refresh must not resurrect logout
      if (active) transition(session);
    });
    return () => {
      active = false;
      unsubscribe();
      invalidateSessionRequests();
      void latest.current.client.cancelQueries();
      latest.current.client.clear();
    };
  }, [backend, transition]);

  const value = useMemo<AuthState>(() => ({
    status: loading ? "loading" : boundary.session ? "signed_in" : "signed_out",
    mode: backend.mode,
    user: boundary.session?.user ?? null,
    getAccessToken: getToken,
    signInWithGoogle: async () => { await logout.current; await backend.signInWithGoogle(); },
    signInWithEmail: async (email) => { await logout.current; await backend.signInWithEmail(email); },
    signInDemo: async () => { await logout.current; await backend.signIn(); },
    signOut,
  }), [backend, boundary.session, getToken, loading, signOut]);

  return <AuthContext.Provider value={value}>
    <QueryClientProvider client={boundary.client}>
      <Fragment key={boundary.version}>{children}</Fragment>
    </QueryClientProvider>
  </AuthContext.Provider>;
}
