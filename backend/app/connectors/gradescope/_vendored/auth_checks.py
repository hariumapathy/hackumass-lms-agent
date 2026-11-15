# Vendored from https://github.com/Yuanpeng-Li/gradescope-mcp @ f8a46c8,
# src/gradescope_mcp/auth.py, MIT License, (c) 2026 Yuanpeng Li
# (full text: LICENSE-gradescope-mcp in this folder).
# Modified: kept only the logged-out / session-expiry checks (`_site`, `_is_login_path`,
# `_has_login_form`, `_is_logged_out_page`, `_content_type`, `_shows_logged_out_page`,
# `_is_logged_out_body`, `_expiry_reason` and the constants they use). Removed the password
# login, credential cooldowns, session recovery, write tracking and timeout adapters. Added
# type hints. `_expiry_reason` is unchanged in logic.
"""Gradescope logged-out page and session-expiry detection."""

import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_LOGIN_PATHS = ("/login", "/account/auth")
_HTML_TYPES = ("text/html", "application/xhtml+xml")
_LOGOUT_URL_RE = re.compile(r"/logout(?:[/?#]|$)", re.IGNORECASE)
# Cheap pre-check before a page is parsed for the login form: an opening
# ``<form`` tag whose action is ``/login`` (relative or absolute).
_LOGIN_FORM_TAG_RE = re.compile(
    rb"<form\b[^>]*\baction\s*=\s*[\"']?(?:https?://[^\"'\s>/]+)?/login(?=[/?#\"'\s>])",
    re.IGNORECASE,
)


def _site(url: str) -> str:
    """Return the URL's host without a leading ``www.`` (for same-site checks)."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_login_path(path: str) -> bool:
    path = path.rstrip("/").lower()
    return any(path == p or path.startswith(p + "/") for p in _LOGIN_PATHS)


def _has_login_form(soup: BeautifulSoup, page_url: str, *, require_password: bool = False) -> bool:
    """Whether the page has a same-site form that posts to the login page.

    The form must carry the password field or (unless ``require_password``)
    the ``authenticity_token`` that ``_login`` scrapes from the home page.
    """
    site = _site(page_url)
    for form in soup.find_all("form"):
        action = urljoin(page_url, str(form.get("action") or ""))
        if _site(action) != site or not _is_login_path(urlsplit(action).path):
            continue
        if form.find("input", attrs={"name": "session[password]"}) is not None:
            return True
        if not require_password and form.find("input", attrs={"name": "authenticity_token"}):
            return True
    return False


def _is_logged_out_page(soup: BeautifulSoup, page_url: str) -> bool:
    """A page with the login form and no logout link (a logged-in page has one)."""
    if soup.find("a", href=_LOGOUT_URL_RE) or soup.find("form", action=_LOGOUT_URL_RE):
        return False
    return _has_login_form(soup, page_url)


def _content_type(response: requests.Response) -> str:
    content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0]
    return content_type.strip().lower()


def _shows_logged_out_page(response: requests.Response, stream: bool = False) -> bool:
    """Whether a page is Gradescope's logged-out page: the login form, no logout link.

    Gradescope may send an expired session to its home page instead of
    ``/login``; requests follows that redirect (turning a POST into a GET),
    and the caller would get a 200 with the anonymous home page. Only HTML is
    inspected (a missing Content-Type counts as HTML).
    """
    content_type = _content_type(response)
    if stream or (content_type and content_type not in _HTML_TYPES):
        return False
    try:
        content = response.content
    except Exception:
        return False
    return _is_logged_out_body(response, content)


def _is_logged_out_body(response: requests.Response, content: bytes) -> bool:
    """Whether ``content``, the body of ``response``, is the logged-out page.

    It is parsed only if it has a ``<form`` tag posting to ``/login``. A page
    that also links to ``/logout`` belongs to a logged-in session and does
    not count.
    """
    if not content or not _LOGIN_FORM_TAG_RE.search(content):
        return False
    try:
        text = content.decode(response.encoding or "utf-8", errors="replace")
    except LookupError:
        text = content.decode("utf-8", errors="replace")
    return _is_logged_out_page(BeautifulSoup(text, "html.parser"), response.url)


def _expiry_reason(response: requests.Response, site: str, stream: bool = False) -> str | None:
    """Return why ``response`` shows an expired session, or None if it doesn't."""
    if _site(response.url) != site:
        return None
    if response.status_code in _REDIRECT_CODES:
        target = urljoin(response.url, response.headers.get("Location") or "")
        if _site(target) == site and _is_login_path(urlsplit(target).path):
            return "redirected to the login page"
        return None
    if _is_login_path(urlsplit(response.url).path):
        return "Gradescope served its login page"
    if response.status_code == 401:
        try:
            body = response.text
        except Exception:
            body = ""
        # A 401 "You are not authorized to access this page." is a permission
        # error on a live session, not an expiry.
        if "must be logged in" in body.lower():
            return "HTTP 401: you must be logged in"
    if 200 <= response.status_code < 300 and _shows_logged_out_page(response, stream):
        return "Gradescope served its logged-out page with the login form"
    return None
