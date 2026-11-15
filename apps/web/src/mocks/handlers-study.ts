import { http, HttpResponse } from "msw";
import type { Fixtures } from "./fixtures";
import { MOCK_API_URL, errorResponse } from "./handlers";

export function studyHandlers(f: Fixtures) {
  const api = (path: string) => `${MOCK_API_URL}${path}`;
  const authed = (request: Request) => (request.headers.get("Authorization") ?? "").startsWith("Bearer ");
  const unauthorized = () => errorResponse(401, "unauthorized", "Sign in again.");
  return [
    http.get(api("/study-sets"), ({ request }) => authed(request)
      ? HttpResponse.json(f.studySets.map(({ id, type, title, course_id, created_at }) => ({ id, type, title, course_id, created_at }))) : unauthorized()),
    http.get(api("/study-sets/:id"), ({ request, params }) => {
      if (!authed(request)) return unauthorized();
      const set = f.studySets.find((s) => s.id === params.id);
      return set ? HttpResponse.json(set) : errorResponse(404, "not_found", "Study set not found.");
    }),
    http.post(api("/study-blocks/decision"), async ({ request }) => {
      if (!authed(request)) return unauthorized();
      const { block_ids, approve } = await request.json() as { block_ids: string[]; approve: boolean };
      const blocks = f.studyBlocks.filter((b) => block_ids.includes(b.id));
      for (const b of blocks) if (b.status === "proposed") b.status = approve ? "approved" : "declined";
      return HttpResponse.json({ blocks });
    }),
  ];
}
