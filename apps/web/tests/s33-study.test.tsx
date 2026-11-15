import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, expect, it } from "vitest";
import { StudyDetail, StudyList } from "@/components/study/study-screen";
import { buildFixtures } from "@/mocks/fixtures";
import { createHandlers, MOCK_API_URL } from "@/mocks/handlers";
import { renderWithProviders } from "./utils";

const f = buildFixtures(new Date("2026-11-14T15:00:00Z"));
const [plan, quiz, cards] = f.studySets;
const server = setupServer(...createHandlers({ fixtures: f }));
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

it("S33-T07 quiz keyboard reveal, explanations, short answer, scoring and retry", async () => {
  renderWithProviders(<StudyDetail id={quiz.id} />);
  const correct = await screen.findByRole("button", { name: "Solutions to subproblems" });
  correct.focus();
  await userEvent.keyboard("{Enter}");
  expect(screen.getByText("Correct!")).toBeInTheDocument();
  expect(screen.getByText("Caching each subproblem avoids repeated work.")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: /Citation 1/ }));
  expect(screen.getByRole("link", { name: /Open source/ })).toHaveAttribute("href", f.citations[0].deep_link);
  await userEvent.keyboard("{Escape}");
  await userEvent.click(screen.getByRole("button", { name: "Next question" }));
  await userEvent.click(screen.getByRole("button", { name: "Accuracy" }));
  expect(screen.getByText(/Not quite/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Next question" }));
  await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
  expect(screen.getByText("Reuse a stored solution instead of solving the same subproblem again.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "See score" }));
  expect(screen.getByText("1 of 2 multiple-choice answers correct")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry quiz" }));
  expect(screen.getByRole("button", { name: "Solutions to subproblems" })).toBeEnabled();
  expect(screen.queryByText("Correct!")).not.toBeInTheDocument();
});

it("S33-T08 flashcards flip with Space, navigate with arrows, shuffle and track piles", async () => {
  renderWithProviders(<StudyDetail id={cards.id} />);
  const card = await screen.findByRole("button", { name: /Flip card/ });
  card.focus();
  await userEvent.keyboard(" ");
  expect(screen.getByText("Caching solutions to subproblems.")).toBeInTheDocument();
  await userEvent.keyboard("{ArrowRight}");
  expect(screen.getByText("What resource does caching use?")).toBeInTheDocument();
  await userEvent.keyboard("{ArrowLeft}");
  expect(screen.getByText("What is memoization?")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Got it" }));
  await userEvent.click(screen.getByRole("button", { name: "Again" }));
  expect(screen.getByText("Got it: 1 · Again: 1")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Shuffle" }));
  expect(screen.getByText("Card 1 of 5")).toBeInTheDocument();
  expect(screen.getByText("Got it: 1 · Again: 1")).toBeInTheDocument();
});

it("S33 plan checkboxes persist per set and display task citations", async () => {
  const view = renderWithProviders(<StudyDetail id={plan.id} />);
  const boxes = await screen.findAllByRole("checkbox");
  await userEvent.click(boxes[0]);
  expect(boxes[0]).toBeChecked();
  view.unmount();
  renderWithProviders(<StudyDetail id={plan.id} />);
  expect((await screen.findAllByRole("checkbox"))[0]).toBeChecked();
  expect(await screen.findAllByRole("button", { name: /Citation 1/ })).toHaveLength(5);
});

it("S33 saved citation map needs no citation lookup", async () => {
  let lookups = 0;
  server.use(
    http.get(`${MOCK_API_URL}/study-sets/${cards.id}`, () => HttpResponse.json({ ...cards, payload: { ...cards.payload, citations: { 8812: f.citations[0], 9930: f.citations[1] } } })),
    http.get(`${MOCK_API_URL}/citations`, () => { lookups++; return HttpResponse.json([]); }),
  );
  renderWithProviders(<StudyDetail id={cards.id} />);
  await userEvent.click(await screen.findByRole("button", { name: /Flip card/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Citation 1/ }));
  expect(screen.getByRole("link", { name: /Open source/ })).toHaveAttribute("href", f.citations[0].deep_link);
  expect(lookups).toBe(0);
});

it("S33 study list links all saved sets and handles an empty list", async () => {
  const view = renderWithProviders(<StudyList />);
  expect(await screen.findByRole("link", { name: /CS 311 dynamic programming quiz/ })).toHaveAttribute("href", `/study/${quiz.id}`);
  expect(screen.getAllByRole("link", { name: /CS 311/ })).toHaveLength(3);
  view.unmount();
  server.use(http.get(`${MOCK_API_URL}/study-sets`, () => HttpResponse.json([])));
  renderWithProviders(<StudyList />);
  expect(await screen.findByText("No study sets yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ask for a study set" })).toHaveAttribute("href", "/chat");
});

it("S33 missing study set offers retry and a way back", async () => {
  renderWithProviders(<StudyDetail id="missing" />);
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again/ })).toBeEnabled();
  expect(screen.getByRole("link", { name: "All study sets" })).toHaveAttribute("href", "/study");
});

it("S33 malformed payload does not crash the study page", async () => {
  server.use(http.get(`${MOCK_API_URL}/study-sets/${quiz.id}`, () => HttpResponse.json({ ...quiz, payload: { questions: [{ type: "mcq" }] } })));
  renderWithProviders(<StudyDetail id={quiz.id} />);
  expect(await screen.findByText("This study set couldn't be opened.")).toBeInTheDocument();
});
