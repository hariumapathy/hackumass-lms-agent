"""S17 test helper: a fake Piazza JSON API (requests adapter) serving hand-written fixtures.

Routes piazza-api's `POST https://piazza.com/logic/api?method=...` calls by method + params; the
real `PiazzaClient` / `PiazzaRPC` code runs unchanged on top. Never touches the network.
"""

import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

from app.connectors.piazza._vendored.client import PiazzaClient, _TimeoutSession
from app.connectors.piazza.connector import PiazzaConnector

FIX = Path(__file__).resolve().parent / "fixtures" / "piazza"
CS311, CS220, OLD = "fakecs311nid", "fakecs220nid", "fakeoldnid"


def fx(name: str) -> Any:
    return json.loads((FIX / name).read_text())


STATE: dict[str, Any] = {
    "cookies": [
        {"name": "session_id", "value": "pz-session", "domain": "piazza.com", "path": "/"},
        {"name": "piazza_session", "value": "pz-cookie", "domain": ".piazza.com", "path": "/"},
        {"name": "shib_idp_session", "value": "sso-secret", "domain": "webauth.umass.edu"},
        {"name": "duo", "value": "duo-secret", "domain": ".duosecurity.com", "path": "/"},
    ],
    "origins": [],
}


class FakePiazza(BaseAdapter):
    """Records (method, params, headers, cookie header) per call."""

    def __init__(self, *, status: int = 200, override: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.status = status
        self.override = override or {}
        self.calls: list[dict[str, Any]] = []
        self.posts = fx("posts_cs311.json")

    def _body(self, method: str, params: dict[str, Any]) -> Any:
        if method in self.override:
            return self.override[method]
        if method == "user.status":
            return fx("user_status.json")
        if method == "network.get_my_feed":
            return fx("feed_cs311.json") if params.get("nid") == CS311 else fx("feed_empty.json")
        if method == "content.get" and params.get("nid") == CS311:
            post = self.posts.get(str(params.get("cid")))
            if post is not None:
                return post
        return {"result": None, "error": "Post not found."}

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        url = str(request.url)
        method = parse_qs(urlsplit(url).query).get("method", [""])[0]
        raw = request.body or b"{}"
        payload = json.loads(raw if isinstance(raw, str | bytes) else b"{}")
        params = payload.get("params", {})
        self.calls.append(
            {
                "http": request.method,
                "url": url,
                "method": method,
                "params": params,
                "csrf": request.headers.get("CSRF-Token"),
                "cookie": request.headers.get("Cookie", ""),
            }
        )
        resp = requests.Response()
        resp.status_code = self.status
        resp._content = json.dumps(self._body(method, params)).encode()  # type: ignore[attr-defined]
        resp._content_consumed = True  # type: ignore[attr-defined]
        resp.raw = io.BytesIO(b"")
        resp.url = url
        resp.encoding = "utf-8"
        resp.headers = CaseInsensitiveDict({"Content-Type": "application/json"})
        resp.request = request
        return resp

    def close(self) -> None:
        pass

    def methods(self) -> list[str]:
        return [c["method"] for c in self.calls]


def make_connector(
    adapter: FakePiazza | None = None, **kwargs: Any
) -> tuple[PiazzaConnector, FakePiazza]:
    fake = adapter or FakePiazza()

    def factory(state: dict[str, Any], min_interval_s: float) -> PiazzaClient:
        session = _TimeoutSession(5.0, min_interval_s=0)
        session.mount("https://", fake)
        session.mount("http://", fake)
        return PiazzaClient.from_storage_state(state, session=session)

    return PiazzaConnector(min_interval_s=0, client_factory=factory, **kwargs), fake
