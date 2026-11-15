import { act, render, screen, waitFor } from "@testing-library/react";
import { http } from "msw";
import { useEffect } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { AppShell } from "@/components/layout/app-shell";
import { RequireAuth } from "@/components/layout/require-auth";
import { api, ApiError, configureApi } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { AuthProvider } from "@/lib/auth/auth-provider";
import { createDemoAuthBackend } from "@/lib/auth/demo-backend";
import { errorResponse, MOCK_API_URL } from "@/mocks/handlers";
import { createMockServer } from "@/mocks/server";
import { navState, routerMock } from "./next-navigation";
import { mockMatchMedia, renderWithProviders } from "./utils";

const server = createMockServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("S30 frontend shell and auth", () => {
  it("S30-T01 protected route redirects to / when signed out", async () => {
    renderWithProviders(
      <RequireAuth>
        <p>secret page</p>
      </RequireAuth>,
      { auth: { status: "signed_out", user: null } },
    );
    await waitFor(() => expect(routerMock.replace).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });

  it("S30-T01 protected route renders children when signed in", () => {
    renderWithProviders(
      <RequireAuth>
        <p>secret page</p>
      </RequireAuth>,
    );
    expect(screen.getByText("secret page")).toBeInTheDocument();
    expect(routerMock.replace).not.toHaveBeenCalled();
  });

  it("S30-T02 API client attaches the bearer token", async () => {
    let seenAuth: string | null = null;
    server.use(
      http.get(`${MOCK_API_URL}/health`, ({ request }) => {
        seenAuth = request.headers.get("Authorization");
        return Response.json({ status: "ok" });
      }),
    );
    configureApi({ getToken: async () => "tok-123", onUnauthorized: () => {} });
    await api().request("GET", "/health");
    expect(seenAuth).toBe("Bearer tok-123");
  });

  it("S30-T02 API client maps the error envelope to ApiError", async () => {
    server.use(
      http.get(`${MOCK_API_URL}/courses/:id`, () => errorResponse(404, "not_found", "Course not found.")),
      http.get(`${MOCK_API_URL}/today`, () => errorResponse(500, "internal", "Boom", true)),
    );
    configureApi({ getToken: async () => "tok", onUnauthorized: () => {} });

    const notFound = await api().course("nope").catch((e) => e);
    expect(notFound).toBeInstanceOf(ApiError);
    expect(notFound).toMatchObject({ code: "not_found", status: 404, retryable: false, message: "Course not found." });

    const internal = await api().today().catch((e) => e);
    expect(internal).toMatchObject({ code: "internal", status: 500, retryable: true });
  });

  it("S30-T02 a non-JSON failure still becomes an ApiError", async () => {
    server.use(http.get(`${MOCK_API_URL}/me`, () => new Response("bad gateway", { status: 502 })));
    configureApi({ getToken: async () => "tok", onUnauthorized: () => {} });
    const err = await api().me().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 502, retryable: true });
  });

  it("S30-T03 a 401 from the API signs out and redirects to /", async () => {
    server.use(http.get(`${MOCK_API_URL}/me`, () => errorResponse(401, "unauthorized", "Sign in again.")));
    const backend = createDemoAuthBackend();
    await backend.signIn();

    function CallsMe() {
      const auth = useAuth();
      useEffect(() => {
        if (auth.status === "signed_in") api().me().catch(() => {});
      }, [auth.status]);
      return <p>status: {auth.status}</p>;
    }

    render(
      <AuthProvider backend={backend}>
        <CallsMe />
      </AuthProvider>,
    );
    await waitFor(() => expect(routerMock.replace).toHaveBeenCalledWith("/"));
    await waitFor(() => expect(screen.getByText("status: signed_out")).toBeInTheDocument());
  });

  it("S30-T06 layout uses a sidebar on desktop", () => {
    mockMatchMedia(true);
    navState.pathname = "/today";
    renderWithProviders(
      <AppShell>
        <p>content</p>
      </AppShell>,
    );
    expect(screen.getByRole("navigation", { name: "Sidebar" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Bottom tabs" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /today/i })).toHaveAttribute("aria-current", "page");
  });

  it("S30-T06 layout uses bottom tabs below 768px", async () => {
    mockMatchMedia(false);
    renderWithProviders(
      <AppShell>
        <p>content</p>
      </AppShell>,
    );
    await act(async () => {});
    expect(screen.getByRole("navigation", { name: "Bottom tabs" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Sidebar" })).not.toBeInTheDocument();
  });
});
