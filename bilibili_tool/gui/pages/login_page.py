from __future__ import annotations

import json

from bilibili_tool.application import AppContext
from bilibili_tool.infra.browser import BrowserCookieCollector, BrowserProfileManager
from bilibili_tool.gui.theme import card_frame, page_root


class LoginPage:
    """登录中心页面，直接承载 B 站页面和本地会话恢复能力。"""

    DEFAULT_SESSION_NAME = "embedded-browser"
    INTRO_DIALOG_SHOWN_THIS_RUN = False

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.state_label = None
        self.save_session_button = None
        self.browser_view = None
        self.browser_profile = None
        self.cookie_collector = None
        self._restored_session_ready = False
        self._last_persisted_cookie_json: str | None = None

    def build(self):
        """构造登录页面，并优先尝试恢复已保存会话。"""

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

        language = self.context.settings.ui_language
        widget, layout = page_root()

        title_label = QLabel("本地登录" if language == "zh-CN" else "Local Login")
        title_label.setObjectName("pageTitle")
        subtitle = QLabel(
            "通过内嵌浏览器完成真实登录，程序会在检测到可用 Cookie 后自动保存本地会话。"
            if language == "zh-CN"
            else "Sign in through the embedded browser. The app saves the local session once required cookies are detected."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle)

        content = QGridLayout()
        content.setSpacing(14)

        browser_panel = card_frame()
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(12, 12, 12, 12)
        browser_layout.setSpacing(10)
        browser_title = QLabel("Bilibili 登录窗口" if language == "zh-CN" else "Bilibili Sign-In Window")
        browser_title.setObjectName("sectionTitle")
        browser_layout.addWidget(browser_title)

        self.state_label = QLabel()
        self.state_label.setObjectName("mutedText")

        browser_widget = self._build_browser_widget()
        browser_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        browser_layout.addWidget(browser_widget, stretch=1)
        content.addWidget(browser_panel, 0, 0)

        side_card = card_frame()
        side_layout = QVBoxLayout(side_card)
        side_layout.setContentsMargins(18, 16, 18, 18)
        side_layout.setSpacing(12)
        side_title = QLabel("会话保存" if language == "zh-CN" else "Session Save")
        side_title.setObjectName("sectionTitle")
        side_layout.addWidget(side_title)
        side_layout.addWidget(self.state_label)
        for cookie_name in ("SESSDATA", "bili_jct", "DedeUserID"):
            chip = QLabel(cookie_name)
            chip.setObjectName("statusPill")
            side_layout.addWidget(chip)
        self.save_session_button = QPushButton()
        self.save_session_button.setObjectName("primaryButton")
        self.save_session_button.setMinimumHeight(38)
        self.save_session_button.clicked.connect(self._save_captured_session)
        side_layout.addWidget(self.save_session_button)
        info = QLabel(
            "会话仅保存在本地数据库和浏览器 profile 中，不会上传到其他服务。"
            if language == "zh-CN"
            else "The session is stored only in the local database and browser profile."
        )
        info.setObjectName("mutedText")
        info.setWordWrap(True)
        side_layout.addWidget(info)
        side_layout.addStretch(1)
        content.addWidget(side_card, 0, 1)
        content.setColumnStretch(0, 3)
        content.setColumnStretch(1, 1)
        layout.addLayout(content, 1)

        self._restore_saved_session()
        self._refresh_capture_summary()
        self._open_initial_page()
        QTimer.singleShot(120, self._show_intro_dialog_if_needed)
        return widget

    def _build_browser_widget(self):
        """创建嵌入式浏览器，并绑定轻量 Cookie 监听。"""

        language = self.context.settings.ui_language
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtWebEngineCore import QWebEnginePage
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWidgets import QLabel
        except ImportError:
            fallback = QLabel(
                "当前环境缺少 Qt WebEngine，无法创建嵌入式浏览器。"
                if language == "zh-CN"
                else "Qt WebEngine is not available in the current environment, so the embedded browser cannot be created."
            )
            fallback.setWordWrap(True)
            return fallback

        profile_manager = BrowserProfileManager(paths=self.context.paths, settings=self.context.settings)
        self.browser_profile = profile_manager.build_profile()
        self.cookie_collector = BrowserCookieCollector(on_changed=self._refresh_capture_summary)
        self.cookie_collector.attach(self.browser_profile)

        page = QWebEnginePage(self.browser_profile, None)
        self.browser_view = QWebEngineView()
        self.browser_view.setPage(page)
        self.browser_view.setMinimumSize(760, 560)
        self.browser_view.loadFinished.connect(self._on_page_loaded)
        self.browser_view.setUrl(QUrl("about:blank"))
        return self.browser_view

    def _restore_saved_session(self) -> None:
        """把已保存的登录会话回填到当前浏览器与按钮状态中。"""

        if self.cookie_collector is None:
            return

        session = self.context.auth_session_repository.get_active()
        if session is None:
            return

        try:
            cookies = json.loads(session.cookie_json)
        except (TypeError, ValueError):
            return

        if not isinstance(cookies, dict):
            return

        normalized = {str(key): str(value) for key, value in cookies.items() if value}
        if not normalized:
            return

        snapshot = self.context.browser_session_service.build_snapshot(normalized)
        self._restored_session_ready = snapshot.is_ready
        self._last_persisted_cookie_json = snapshot.cookie_json
        self.cookie_collector.import_cookies(normalized, notify=False)
        self.cookie_collector.restore_to_store(normalized)

    def _open_initial_page(self) -> None:
        """根据当前是否已有本地会话，选择更合适的起始页面。"""

        if self.browser_view is None:
            return

        from PySide6.QtCore import QUrl

        if self._restored_session_ready:
            self.browser_view.setUrl(QUrl("https://www.bilibili.com/"))
        else:
            self.browser_view.setUrl(QUrl("https://passport.bilibili.com/login"))

    def _refresh_state(self, snapshot_ready: bool) -> None:
        """刷新顶部状态文案。"""

        language = self.context.settings.ui_language
        login_state = self.context.auth_service.get_login_state()
        if login_state.is_logged_in and snapshot_ready:
            text = "当前状态：已恢复本地登录" if language == "zh-CN" else "Current state: local session restored"
        elif snapshot_ready:
            text = "当前状态：已检测到登录信息" if language == "zh-CN" else "Current state: session detected"
        else:
            text = "当前状态：等待登录" if language == "zh-CN" else "Current state: waiting for sign-in"
        self.state_label.setText(text)

    def _refresh_capture_summary(self) -> None:
        """根据当前捕获到的 Cookie 更新按钮、状态与自动保存逻辑。"""

        language = self.context.settings.ui_language
        cookies = self.cookie_collector.export_cookies() if self.cookie_collector is not None else {}
        snapshot = self.context.browser_session_service.build_snapshot(cookies)

        if snapshot.is_ready and snapshot.cookie_json != self._last_persisted_cookie_json:
            self._persist_session(cookies, automatic=True)
            return

        if snapshot.is_ready:
            self.save_session_button.setEnabled(False)
            self.save_session_button.setText("会话已同步" if language == "zh-CN" else "Session Synced")
            self.save_session_button.setToolTip(
                "当前登录会话已经自动同步到本地。"
                if language == "zh-CN"
                else "The current browser session has already been synchronized locally."
            )
        else:
            missing = ", ".join(snapshot.missing_cookie_names) if snapshot.missing_cookie_names else "-"
            self.save_session_button.setEnabled(False)
            self.save_session_button.setText("等待登录完成" if language == "zh-CN" else "Waiting For Sign-In")
            self.save_session_button.setToolTip(
                f"尚未满足保存条件，缺少：{missing}"
                if language == "zh-CN"
                else f"The session is not ready yet. Missing: {missing}"
            )

        self._refresh_state(snapshot_ready=snapshot.is_ready)

    def _persist_session(self, cookies: dict[str, str], automatic: bool) -> None:
        """把当前 Cookie 保存到本地，并更新页面按钮状态。"""

        language = self.context.settings.ui_language
        try:
            self.context.browser_session_service.save_captured_session(
                session_name=self.DEFAULT_SESSION_NAME,
                cookies=cookies,
            )
        except ValueError as exc:
            self.save_session_button.setEnabled(False)
            self.save_session_button.setText("暂不可保存" if language == "zh-CN" else "Not Ready To Save")
            self.save_session_button.setToolTip(str(exc))
            return

        snapshot = self.context.browser_session_service.build_snapshot(cookies)
        self._last_persisted_cookie_json = snapshot.cookie_json
        self._restored_session_ready = snapshot.is_ready
        self.context.settings = self.context.settings_service.dismiss_login_intro()
        self.save_session_button.setEnabled(False)
        self.save_session_button.setText("会话已自动更新" if language == "zh-CN" else "Session Auto-Saved")
        self.save_session_button.setToolTip(
            "当前浏览器会话已经自动保存到本地。"
            if language == "zh-CN"
            else "The current browser session has been saved locally."
        )
        self._refresh_state(snapshot_ready=True)

    def _save_captured_session(self) -> None:
        """保留手动入口作为兜底，但正常情况下会自动更新。"""

        cookies = self.cookie_collector.export_cookies() if self.cookie_collector is not None else {}
        self._persist_session(cookies, automatic=False)

    def _on_page_loaded(self, success: bool) -> None:
        """页面加载完成后只做一次轻量缩放。"""

        if not success or self.browser_view is None:
            return

        width = max(self.browser_view.width(), 760)
        height = max(self.browser_view.height(), 560)
        width_scale = width / 1180
        height_scale = height / 760
        zoom_factor = max(0.82, min(1.0, width_scale, height_scale))
        self.browser_view.setZoomFactor(zoom_factor)

    def _show_intro_dialog_if_needed(self) -> None:
        """首次进入登录页时弹出说明，并在保存过会话后停止出现。"""

        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None or app.platformName() == "offscreen":
            return

        if LoginPage.INTRO_DIALOG_SHOWN_THIS_RUN:
            return

        if self.context.auth_service.get_login_state().is_logged_in:
            if self.context.settings.show_login_intro_dialog:
                self.context.settings = self.context.settings_service.dismiss_login_intro()
            return

        if not self.context.settings.show_login_intro_dialog:
            return

        language = self.context.settings.ui_language
        title = "登录说明" if language == "zh-CN" else "Login Notice"
        message = (
            "这个页面会直接打开 B 站页面。\n\n"
            "如果本地已经有可用会话，程序会先尝试恢复它；如果没有，再让你继续登录。"
            "当检测到 SESSDATA、bili_jct 和 DedeUserID 后，程序会自动把当前会话保存到本地。"
            if language == "zh-CN"
            else "This page opens the bilibili page directly.\n\n"
            "If a local session is available, the app tries to restore it first. Otherwise, you can continue signing in. "
            "Once SESSDATA, bili_jct, and DedeUserID are detected, the app saves the current session automatically."
        )
        QMessageBox.information(None, title, message)
        LoginPage.INTRO_DIALOG_SHOWN_THIS_RUN = True
