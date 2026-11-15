import { expect, test } from "@playwright/test";

test("S33-T11 ask, stream, open quiz, answer, approve sessions", async ({ page, context }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByRole("button", { name: /continue with demo data/i }).click();
  await expect(page).toHaveURL(/\/today$/);
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await page.getByRole("textbox", { name: "Message" }).fill("Prep me for the CS 311 midterm");
  await page.getByRole("textbox", { name: "Message" }).press("Enter");
  const quizLink = page.getByRole("link", { name: /Practice quiz/ });
  await expect(quizLink).toBeVisible();
  // Keep the proposal in its live chat while reviewing the linked study set.
  const quiz = await context.newPage();
  await quiz.goto((await quizLink.getAttribute("href"))!);
  await quiz.getByRole("button", { name: "Solutions to subproblems" }).click();
  await expect(quiz.getByText("Correct!", { exact: true })).toBeVisible();
  await quiz.getByRole("button", { name: /Citation 1/ }).click();
  await expect(quiz.getByRole("link", { name: /Open source/ })).toHaveAttribute("href", /example\.instructure\.com/);
  await quiz.close();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Added. They'll show up in your calendar app on its next refresh.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Skip", exact: true })).toBeDisabled();
});
