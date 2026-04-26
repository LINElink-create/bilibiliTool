from __future__ import annotations

from collections.abc import Callable

from bilibili_tool.application import AppContext
from bilibili_tool.gui.i18n import language_display_name, language_options, t
from bilibili_tool.gui.theme import card_frame, page_root


class SettingsPage:
    """设置页面，展示语言、路径和下载相关配置。"""

    def __init__(self, context: AppContext, on_language_changed: Callable[[], None]) -> None:
        self.context = context
        self.on_language_changed = on_language_changed
        self.language_combo = None
        self.download_concurrency_spin = None
        self.status_label = None
        self.current_label = None

    def build(self):
        """构造卡片化设置页面。"""

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout

        language = self.context.settings.ui_language
        widget, layout = page_root()
        title = QLabel(t(language, "settings.title"))
        title.setObjectName("pageTitle")
        subtitle = QLabel(t(language, "settings.language_help"))
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(14)

        general_card = card_frame()
        general_layout = QGridLayout(general_card)
        general_layout.setContentsMargins(18, 16, 18, 18)
        general_layout.setHorizontalSpacing(12)
        general_layout.setVerticalSpacing(10)
        general_title = QLabel(self._text("通用设置", "General"))
        general_title.setObjectName("sectionTitle")
        self.language_combo = QComboBox()
        for code, label in language_options():
            self.language_combo.addItem(label, code)
        index = self.language_combo.findData(language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        save_button = QPushButton(t(language, "settings.save_language"))
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_language)
        self.current_label = QLabel(t(language, "settings.current_language", value=language_display_name(self.context.settings.ui_language)))
        self.current_label.setObjectName("mutedText")
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")
        general_layout.addWidget(general_title, 0, 0, 1, 2)
        general_layout.addWidget(QLabel(t(language, "settings.language_label")), 1, 0)
        general_layout.addWidget(self.language_combo, 1, 1)
        general_layout.addWidget(save_button, 2, 1)
        general_layout.addWidget(self.current_label, 3, 0, 1, 2)
        general_layout.addWidget(self.status_label, 4, 0, 1, 2)
        grid.addWidget(general_card, 0, 0)

        download_card = card_frame()
        download_layout = QGridLayout(download_card)
        download_layout.setContentsMargins(18, 16, 18, 18)
        download_layout.setHorizontalSpacing(12)
        download_layout.setVerticalSpacing(10)
        download_title = QLabel(self._text("下载设置", "Download Settings"))
        download_title.setObjectName("sectionTitle")
        self.download_concurrency_spin = QSpinBox()
        self.download_concurrency_spin.setRange(1, 8)
        self.download_concurrency_spin.setValue(self.context.settings.download_concurrency)
        save_download_button = QPushButton(self._text("保存设置", "Save Settings"))
        save_download_button.setObjectName("primaryButton")
        save_download_button.clicked.connect(self._save_download_settings)
        download_layout.addWidget(download_title, 0, 0, 1, 2)
        download_layout.addWidget(QLabel(self._text("并发数量", "Concurrency")), 1, 0)
        download_layout.addWidget(self.download_concurrency_spin, 1, 1)
        download_layout.addWidget(save_download_button, 2, 1)
        hint = QLabel(self._text("并发设置会保存到本地配置，下载执行器会按当前实现逐步使用。", "Concurrency is saved locally and used by the downloader as supported."))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        download_layout.addWidget(hint, 3, 0, 1, 2)
        grid.addWidget(download_card, 0, 1)

        path_card = card_frame()
        path_layout = QGridLayout(path_card)
        path_layout.setContentsMargins(18, 16, 18, 18)
        path_layout.setHorizontalSpacing(12)
        path_layout.setVerticalSpacing(10)
        path_title = QLabel(self._text("数据目录", "Data Directories"))
        path_title.setObjectName("sectionTitle")
        data_path = QLineEdit(str(self.context.paths.data_dir))
        downloads_path = QLineEdit(str(self.context.paths.downloads_dir))
        browser_path = QLineEdit(str(self.context.paths.browser_profile_dir))
        for field in (data_path, downloads_path, browser_path):
            field.setReadOnly(True)
        open_data_button = QPushButton(self._text("打开数据目录", "Open Data Directory"))
        open_data_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.data_dir))))
        open_downloads_button = QPushButton(self._text("打开下载目录", "Open Downloads"))
        open_downloads_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.downloads_dir))))
        path_layout.addWidget(path_title, 0, 0, 1, 3)
        path_layout.addWidget(QLabel(self._text("数据", "Data")), 1, 0)
        path_layout.addWidget(data_path, 1, 1, 1, 2)
        path_layout.addWidget(QLabel(self._text("下载", "Downloads")), 2, 0)
        path_layout.addWidget(downloads_path, 2, 1, 1, 2)
        path_layout.addWidget(QLabel(self._text("浏览器会话", "Browser Session")), 3, 0)
        path_layout.addWidget(browser_path, 3, 1, 1, 2)
        buttons = QHBoxLayout()
        buttons.addWidget(open_data_button)
        buttons.addWidget(open_downloads_button)
        buttons.addStretch(1)
        path_layout.addLayout(buttons, 4, 1, 1, 2)
        grid.addWidget(path_card, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid, 1)
        return widget

    def _save_language(self) -> None:
        """保存当前选择的语言，并通知主窗口重建界面。"""

        language_code = self.language_combo.currentData()
        saved_settings = self.context.settings_service.set_ui_language(language_code)
        self.context.settings = saved_settings
        self.status_label.setText(t(saved_settings.ui_language, "settings.status_saved"))
        self.current_label.setText(
            t(saved_settings.ui_language, "settings.current_language", value=language_display_name(saved_settings.ui_language))
        )
        self.on_language_changed()

    def _save_download_settings(self) -> None:
        """保存下载相关设置。"""

        saved_settings = self.context.settings_service.set_download_concurrency(self.download_concurrency_spin.value())
        self.context.settings = saved_settings
        self.status_label.setText(self._text("下载设置已保存。", "Download settings saved."))

    def _text(self, zh: str, en: str) -> str:
        """返回当前语言文案。"""

        return zh if self.context.settings.ui_language == "zh-CN" else en
