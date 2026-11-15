import { expect, test } from "@playwright/test";

test("S32-T08 Today -> course page -> back", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();

  await page.getByRole("link", { name: "COMPSCI 311" }).first().click();
  await expect(page).toHaveURL(/\/courses\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { level: 1, name: /COMPSCI 311/ })).toBeVisible();
  await expect(page.getByText("Midterm 1").first()).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();
});
