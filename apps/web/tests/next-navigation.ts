import { vi } from "vitest";

export const routerMock = {
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
};

export const navState: { pathname: string; search: string; params: Record<string, string> } = {
  pathname: "/",
  search: "",
  params: {},
};
