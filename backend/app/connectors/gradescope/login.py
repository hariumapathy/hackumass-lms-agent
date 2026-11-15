"""S14: Gradescope's live-login recipe for S13. The student picks "School Credentials" → UMass
Amherst → NetID + Duo in the real window; we only watch for Gradescope's logged-in account page.
"""

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.connectors.browser.types import LoginSpec, PageLike
from app.connectors.gradescope._vendored.auth_checks import (
    _LOGOUT_URL_RE,
    _is_logged_out_page,
    _is_login_path,
)

GRADESCOPE_BASE_URL = "https://www.gradescope.com"


def _is_gradescope_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "gradescope.com" or host.endswith(".gradescope.com")


def page_shows_logged_in(url: str, html: str) -> bool:
    """A Gradescope page (not /login) with a logout link or the account course list."""
    if not _is_gradescope_host(url) or _is_login_path(urlsplit(url).path):
        return False
    soup = BeautifulSoup(html, "html.parser")
    if _is_logged_out_page(soup, url):
        return False
    has_logout = soup.find("a", href=_LOGOUT_URL_RE) is not None
    has_courses = soup.select_one("#account-show, .courseList") is not None
    return has_logout or has_courses


async def is_logged_in(page: PageLike) -> bool:
    url = page.url
    if not _is_gradescope_host(url):  # still on UMass SSO / Duo
        return False
    return page_shows_logged_in(url, await page.content())


GRADESCOPE_LOGIN = LoginSpec(
    platform="gradescope",
    start_url=f"{GRADESCOPE_BASE_URL}/login",
    is_logged_in=is_logged_in,
    check_url=f"{GRADESCOPE_BASE_URL}/account",
)
