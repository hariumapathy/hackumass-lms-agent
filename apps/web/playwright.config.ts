import { defineConfig, devices } from "@playwright/test";

// E2E tests live in tests/e2e. On PRs they run against MSW mocks (S30); against the real stack at checkpoints.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://localhost:3100",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Mock mode: MSW serves the S02 API and the demo sign-in stands in for Supabase (S30 rule 5).
    command: "pnpm dev --port 3100",
    env: { NEXT_PUBLIC_API_MOCKS: "1", NEXT_PUBLIC_SUPABASE_URL: "", NEXT_PUBLIC_SUPABASE_ANON_KEY: "" },
    url: "http://localhost:3100",
    reuseExistingServer: !process.env.CI,
  },
});
