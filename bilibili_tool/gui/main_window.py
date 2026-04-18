from __future__ import annotations

from bilibili_tool.application import AppContext
from bilibili_tool.gui.i18n import t
from bilibili_tool.gui.pages import DashboardPage, DownloadsPage, LibraryPage, LoginPage, SettingsPage, SourcesPage


def run_desktop_app(context: AppContext) -> int:
    """启动桌面外壳，并支持界面语言的即时切换。"""

    try:
        from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
    except ImportError:
        print("PySide6 is not installed. Install project dependencies to launch the desktop shell.")
        return 1

    app = QApplication([])
    window = QMainWindow()
    window.resize(1280, 820)

    def rebuild_ui() -> None:
        """根据当前语言重新构造整套标签页，并保留页面对象引用。"""

        language = context.settings.ui_language
        window.setWindowTitle(t(language, "app.title"))

        dashboard_page = DashboardPage(context)
        sources_page = SourcesPage(context)
        library_page = LibraryPage(context)
        downloads_page = DownloadsPage(context)
        login_page = LoginPage(context)
        settings_page = SettingsPage(context, on_language_changed=rebuild_ui)

        # 保留页面对象引用，避免 Qt 槽绑定的 Python 实例被垃圾回收。
        page_refs = {
            "dashboard": dashboard_page,
            "sources": sources_page,
            "library": library_page,
            "downloads": downloads_page,
            "login": login_page,
            "settings": settings_page,
        }
        window._page_refs = page_refs

        sources_page.set_after_sync_callback(library_page.refresh)

        tabs = QTabWidget()
        tabs._page_refs = page_refs
        tabs.addTab(dashboard_page.build(), t(language, "nav.dashboard"))
        tabs.addTab(sources_page.build(), t(language, "nav.sources"))
        tabs.addTab(library_page.build(), t(language, "nav.library"))
        tabs.addTab(downloads_page.build(), t(language, "nav.downloads"))
        tabs.addTab(login_page.build(), t(language, "nav.login"))
        tabs.addTab(settings_page.build(), t(language, "nav.settings"))
        window.setCentralWidget(tabs)

    rebuild_ui()
    window.show()
    return app.exec()
