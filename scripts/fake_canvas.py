"""Fake Canvas API on 127.0.0.1:8765 for an end-to-end rehearsal (serves the S11 test fixtures).

Run from backend/: uv run python ../scripts/fake_canvas.py
Then run the API + worker with DATA_SOURCE=db CANVAS_BASE_URL=http://127.0.0.1:8765
EMBEDDINGS_PROVIDER=fake and connect Canvas with any token (see docs/progress/neal.md).
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import fitz  # PyMuPDF

FX = json.loads(Path("tests/fixtures/canvas/canvas_api.json").read_text())


def make_pdf() -> bytes:
    doc = fitz.open()
    for text in [
        "Lecture 7: Dynamic Programming. Memoization stores solutions to subproblems.",
        "Weighted interval scheduling: OPT(j) = max(v_j + OPT(p(j)), OPT(j-1)).",
    ]:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    return doc.tobytes()


PDF = make_pdf()


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: ANN001, ANN002
        print("canvas:", self.command, self.path[:90], flush=True)

    def send(self, code: int, body: object, ctype: str = "application/json") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            return self.send(401, FX["unauthorized"])
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        ctx = (q.get("context_codes[]") or [""])[0]
        routes = {
            "/api/v1/users/self": lambda: FX["users_self"],
            "/api/v1/courses": lambda: FX["courses"],
            "/api/v1/courses/12345": lambda: FX["course_12345"],
            "/api/v1/courses/23456": lambda: FX["course_23456"],
            "/api/v1/courses/12345/assignments": lambda: FX["assignments_12345"],
            "/api/v1/courses/23456/assignments": lambda: FX["assignments_23456"],
            "/api/v1/courses/12345/files": lambda: FX["files_12345"],
            "/api/v1/courses/23456/modules": lambda: FX["modules_23456"],
            "/api/v1/courses/23456/files/701": lambda: FX["file_23456_701"],
            "/api/v1/courses/23456/files/702": lambda: FX["file_23456_702"],
        }
        if p == "/api/v1/calendar_events":
            return self.send(200, FX["calendar_events_12345"] if ctx == "course_12345" else [])
        if p == "/api/v1/announcements":
            return self.send(200, FX["announcements_12345"] if ctx == "course_12345" else [])
        if p == "/api/v1/courses/23456/files":
            return self.send(403, FX["forbidden"])
        if re.fullmatch(r"(/api/v1)?/files/\d+/download", p) or re.fullmatch(
            r"/courses/\d+/files/\d+/download", p
        ):
            return self.send(200, PDF, "application/pdf")
        if p in routes:
            return self.send(200, routes[p]())
        return self.send(404, {"errors": [{"message": "not found"}]})


if __name__ == "__main__":
    print("fake canvas on http://127.0.0.1:8765", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
