import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { AuthContext, type AuthState } from "@/lib/auth/auth-context";
import { configureApi } from "@/lib/api/client";

export function fakeAuth(overrides: Partial<AuthState> = {}): AuthState {
  return {
    status: "signed_in",
    mode: "demo",
    user: { id: "u-test", email: "demo@example.com" },
    getAccessToken: async () => "test-token",
    signInWithGoogle: vi.fn(async () => {}),
    signInWithEmail: vi.fn(async () => {}),
    signInDemo: vi.fn(async () => {}),
    signOut: vi.fn(async () => {}),
    ...overrides,
  };
}

export function renderWithProviders(ui: ReactElement, opts: { auth?: Partial<AuthState> } = {}) {
  const auth = fakeAuth(opts.auth);
  configureApi({ getToken: auth.getAccessToken, onUnauthorized: () => {} });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  );
  return { ...render(ui, { wrapper: Wrapper }), auth, queryClient };
}

export function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
