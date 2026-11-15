"""S17: Piazza's live-login recipe for S13. The student signs in in the real window (Piazza
email/password, or "Log in with school credentials" → UMass NetID + Duo); we never read the form
and only watch for a logged-in Piazza class page (`/class...`).
"""

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.connectors.browser.types import LoginSpec, PageLike

PIAZZA_BASE_URL = "https://piazza.com"

_LOGIN_PATHS = ("/account/login", "/signup", "/login", "/account/password")


def _is_piazza_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "piazza.com" or host.endswith(".piazza.com")


def page_shows_logged_in(url: str, html: str) -> bool:
    """A piazza.com `/class` page (logged-out visits redirect to the login page) with no
    password field on it."""
    if not _is_piazza_host(url):
        return False
    path = urlsplit(url).path.rstrip("/").lower()
    if any(path.startswith(p) for p in _LOGIN_PATHS):
        return False
    if not (path == "/class" or path.startswith("/class/")):
        return False
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("input", attrs={"type": "password"}) is not None:
        return False
    return bool(soup.get_text(strip=True) or soup.find("script"))


async def is_logged_in(page: PageLike) -> bool:
    url = page.url
    if not _is_piazza_host(url):  # still on the school SSO / Duo
        return False
    return page_shows_logged_in(url, await page.content())


PIAZZA_LOGIN = LoginSpec(
    platform="piazza",
    start_url=f"{PIAZZA_BASE_URL}/account/login",
    is_logged_in=is_logged_in,
    check_url=f"{PIAZZA_BASE_URL}/class",
)
