import { expect, test } from "@playwright/test";

// Runs in mock mode (NEXT_PUBLIC_API_MOCKS=1, no Supabase env): the demo sign-in stands in for Supabase.
test("S30-T07 sign in lands on /today", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();
});
