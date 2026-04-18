"""Browser integration helpers for embedded login flows."""

from bilibili_tool.infra.browser.cookie_bridge import BrowserCookieCollector
from bilibili_tool.infra.browser.user_search import BrowserUserSearch
from bilibili_tool.infra.browser.webengine_profile import BrowserProfileManager

__all__ = ["BrowserCookieCollector", "BrowserProfileManager", "BrowserUserSearch"]
