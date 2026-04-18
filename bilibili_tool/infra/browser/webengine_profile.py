from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.config import AppPaths, AppSettings


@dataclass(slots=True)
class BrowserProfileManager:
    """创建并配置嵌入式浏览器共用的持久化 profile。"""

    paths: AppPaths
    settings: AppSettings

    def build_profile(self, parent=None):
        """返回一个共享的 Qt WebEngine profile。"""

        from PySide6.QtWebEngineCore import QWebEngineProfile

        self.paths.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.paths.browser_profile_dir / "cache"
        storage_path = self.paths.browser_profile_dir / "storage"
        cache_path.mkdir(parents=True, exist_ok=True)
        storage_path.mkdir(parents=True, exist_ok=True)

        profile = QWebEngineProfile.defaultProfile()
        profile.setCachePath(str(cache_path))
        profile.setPersistentStoragePath(str(storage_path))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        profile.setHttpUserAgent(self.settings.user_agent)
        return profile
