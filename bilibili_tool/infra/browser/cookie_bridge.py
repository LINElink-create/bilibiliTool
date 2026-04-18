from __future__ import annotations

import json
from typing import Callable


class BrowserCookieCollector:
    """监听并收集嵌入式浏览器中的 B 站关键 Cookie。"""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        self.on_changed = on_changed
        self.cookies: dict[str, str] = {}
        self._cookie_store = None

    def attach(self, profile) -> None:
        """把收集器挂到 Qt WebEngine 的 CookieStore 上。"""

        cookie_store = profile.cookieStore()
        cookie_store.cookieAdded.connect(self.capture_cookie)
        self._cookie_store = cookie_store

    def capture_cookie(self, cookie) -> None:
        """收集一条来自 B 站域名的 Cookie。"""

        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        value = bytes(cookie.value()).decode("utf-8", errors="ignore")
        domain = str(cookie.domain()).lstrip(".")
        if not name or not value:
            return
        if "bilibili.com" not in domain:
            return
        self.cookies[name] = value
        if self.on_changed is not None:
            try:
                self.on_changed()
            except RuntimeError:
                return

    def import_cookies(self, cookies: dict[str, str], notify: bool = True) -> None:
        """把已保存的 Cookie 快照回填到当前收集器。"""

        updated = False
        for name, value in cookies.items():
            if not name or not value:
                continue
            self.cookies[name] = value
            updated = True
        if updated and notify and self.on_changed is not None:
            try:
                self.on_changed()
            except RuntimeError:
                return

    def restore_to_store(self, cookies: dict[str, str]) -> None:
        """把已保存的 Cookie 回写到浏览器 CookieStore，恢复登录态。"""

        if self._cookie_store is None:
            return

        from PySide6.QtCore import QDateTime, QUrl
        from PySide6.QtNetwork import QNetworkCookie

        expires = QDateTime.currentDateTimeUtc().addDays(30)
        target_url = QUrl("https://www.bilibili.com/")

        for name, value in cookies.items():
            if not name or not value:
                continue
            cookie = QNetworkCookie(name.encode("utf-8"), value.encode("utf-8"))
            cookie.setDomain(".bilibili.com")
            cookie.setPath("/")
            cookie.setExpirationDate(expires)
            cookie.setSecure(True)
            self._cookie_store.setCookie(cookie, target_url)

    def export_cookies(self) -> dict[str, str]:
        """导出当前已捕获的 Cookie 字典。"""

        return dict(self.cookies)

    def export_cookie_json(self) -> str:
        """把当前已捕获的 Cookie 导出为 JSON 字符串。"""

        return json.dumps(self.cookies, ensure_ascii=False, sort_keys=True)

    def clear(self) -> None:
        """清空当前缓存的 Cookie 快照。"""

        self.cookies.clear()
        if self.on_changed is not None:
            try:
                self.on_changed()
            except RuntimeError:
                return
