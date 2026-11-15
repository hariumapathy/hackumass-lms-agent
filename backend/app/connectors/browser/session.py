"""S13 `check_session`: does a saved storage state still open a logged-in page?

Connectors that read with HTTP (Gradescope via `gradescopeapi`) do their own logged-out checks;
this browser-based check is for platforms that need a real page (Echo360) and for manual checks.
"""

from typing import Any

from app.connectors.browser.manager import login_spec_for
from app.connectors.browser.types import BrowserProvider, LoginSpec


async def check_session(
    platform: str,
    state: dict[str, Any],
    provider: BrowserProvider,
    spec: LoginSpec | None = None,
) -> bool:
    """Open `spec.check_url` headless with saved cookies; False when it lands on a login page."""
    spec = spec or login_spec_for(platform)
    session = await provider.open_with_state(state)
    try:
        page = await session.new_page()
        await page.goto(spec.check_url)
        return await spec.is_logged_in(page)
    except Exception:
        return False
    finally:
        await session.close()
