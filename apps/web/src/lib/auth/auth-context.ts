"use client";

import { createContext, useContext } from "react";

export type AuthStatus = "loading" | "signed_in" | "signed_out";

export interface AuthUser {
  id: string;
  email: string | null;
}

export interface AuthState {
  status: AuthStatus;
  /** "supabase" = real sign-in; "demo" = mock mode without Supabase (dev + e2e only). */
  mode: "supabase" | "demo";
  user: AuthUser | null;
  getAccessToken: () => Promise<string | null>;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string) => Promise<void>;
  signInDemo: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
