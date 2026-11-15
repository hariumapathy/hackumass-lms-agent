import { expect, test } from "@playwright/test";

// The demo account already has Canvas linked and Piazza needing a reconnect, so onboarding resumes at the
// UMass login step (S31 rule 5) and the mocked live login succeeds after one "pending" poll.
test("S31-T06 onboarding (mocked): UMass login -> calendar -> getting your classes -> Today", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();

  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: /connect gradescope and piazza/i })).toBeVisible();
  await page.getByRole("button", { name: /connect piazza/i }).click();
  await expect(page.getByText(/waiting for login/i)).toBeVisible();
  await expect(page.getByText(/piazza connected/i)).toBeVisible();
  await page.getByRole("button", { name: /^continue$/i }).click();

  await expect(page.getByRole("heading", { name: /add your deadlines to your calendar/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /add to google calendar/i })).toHaveAttribute(
    "href",
    /^https:\/\/calendar\.google\.com\/calendar\/r\?cid=webcal/,
  );
  await page.getByRole("button", { name: /^skip$/i }).click();

  const goToday = page.getByRole("button", { name: /go to today/i });
  await expect(goToday).toBeEnabled();
  await goToday.click();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole("heading", { level: 1, name: /today/i })).toBeVisible();
});

test("S31-T05 reconnect from Today's sources bar returns to Settings", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await page.getByRole("link", { name: /reconnect piazza/i }).first().click();

  await expect(page).toHaveURL(/\/onboarding\?reconnect=piazza$/);
  await expect(page.getByRole("heading", { name: /reconnect piazza/i })).toBeVisible();
  await page.getByRole("button", { name: /connect piazza/i }).click();
  await expect(page).toHaveURL(/\/settings$/);
});
