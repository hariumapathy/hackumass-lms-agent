import { expect, test, type Page } from "@playwright/test";

// S33 + S30 rule 1 (mobile): the message box is always reachable above the bottom tab bar.
async function boxes(page: Page) {
  const composer = await page.getByRole("textbox", { name: /message/i }).boundingBox();
  const tabs = await page.getByRole("navigation", { name: "Bottom tabs" }).boundingBox();
  return { composer: composer!, tabs: tabs! };
}

test("S33-T12 phone: the message box sits above the bottom tabs, empty and after a long chat", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();

  await page.goto("/chat");
  const box = page.getByRole("textbox", { name: /message/i });
  await expect(box).toBeVisible();
  let b = await boxes(page);
  expect(b.composer.y + b.composer.height).toBeLessThanOrEqual(b.tabs.y);
  expect(b.composer.y).toBeGreaterThan(812 / 2); // at the bottom of the screen, not mid-page

  for (const q of ["What's due this week?", "Prep me for the CS 311 midterm", "Did anything change?"]) {
    await box.fill(q);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: /send/i })).toBeVisible({ timeout: 30_000 });
  }
  await page.mouse.wheel(0, -5000); // scroll up through the conversation
  await page.waitForTimeout(300);
  b = await boxes(page);
  expect(b.composer.y).toBeGreaterThanOrEqual(0);
  expect(b.composer.y + b.composer.height).toBeLessThanOrEqual(b.tabs.y);
});
