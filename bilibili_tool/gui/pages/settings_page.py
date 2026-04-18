from __future__ import annotations

from collections.abc import Callable

from bilibili_tool.application import AppContext
from bilibili_tool.gui.i18n import language_display_name, language_options, t


class SettingsPage:
    """设置页面，当前负责界面语言的查看与切换。"""

    def __init__(self, context: AppContext, on_language_changed: Callable[[], None]) -> None:
        self.context = context
        self.on_language_changed = on_language_changed
        self.language_combo = None
        self.status_label = None
        self.current_label = None

    def build(self):
        """构造设置页面，并提供语言切换入口。"""

        from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

        language = self.context.settings.ui_language

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"<h3>{t(language, 'settings.title')}</h3>"))
        layout.addWidget(QLabel(t(language, "settings.language_help")))

        group = QGroupBox(t(language, "settings.language_group"))
        form_layout = QFormLayout(group)

        self.language_combo = QComboBox()
        for code, label in language_options():
            self.language_combo.addItem(label, code)
        index = self.language_combo.findData(language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        save_button = QPushButton(t(language, "settings.save_language"))
        save_button.clicked.connect(self._save_language)

        self.current_label = QLabel(
            t(language, "settings.current_language", value=language_display_name(self.context.settings.ui_language))
        )
        self.status_label = QLabel("")

        form_layout.addRow(t(language, "settings.language_label"), self.language_combo)
        form_layout.addRow(save_button)
        form_layout.addRow(self.current_label)
        form_layout.addRow(self.status_label)

        layout.addWidget(group)
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
