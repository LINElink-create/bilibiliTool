from __future__ import annotations

from bilibili_tool.application import AppContext


class DashboardPage:
    """首页页面，集中展示当前工作区的本地统计信息。"""

    def __init__(self, context: AppContext) -> None:
        self.context = context

    def build(self):
        """构造首页控件并填充当前统计信息。"""

        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        from bilibili_tool.gui.i18n import t

        language = self.context.settings.ui_language
        summary = self.context.dashboard_service.build_summary()

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h2>bilibiliTool Desktop</h2>"))
        layout.addWidget(QLabel(self._text(language, "This build focuses on a local-first desktop workflow with controlled network requests.")))
        layout.addWidget(QLabel(self._text(language, "Tracked sources: {value}", value=summary.source_count)))
        layout.addWidget(QLabel(self._text(language, "Cached videos: {value}", value=summary.video_count)))
        layout.addWidget(QLabel(self._text(language, "Download tasks: {value}", value=summary.download_count)))
        layout.addWidget(QLabel(self._text(language, "Active session: {value}", value=summary.active_session_name)))
        layout.addWidget(QLabel(self._text(language, "Database path: {value}", value=self.context.paths.database_path)))
        layout.addWidget(QLabel(self._text(language, "Logs directory: {value}", value=self.context.paths.logs_dir)))
        return widget

    def _text(self, language: str, english: str, **kwargs: object) -> str:
        """为首页提供少量内联双语文案，避免引入过大的翻译表。"""

        chinese_map = {
            "This build focuses on a local-first desktop workflow with controlled network requests.": "当前版本以本地优先的桌面工作流为主，并严格控制联网请求频率。",
            "Tracked sources: {value}": "已追踪来源：{value}",
            "Cached videos: {value}": "本地视频数：{value}",
            "Download tasks: {value}": "下载任务数：{value}",
            "Active session: {value}": "当前会话：{value}",
            "Database path: {value}": "数据库路径：{value}",
            "Logs directory: {value}": "日志目录：{value}",
        }
        template = chinese_map[english] if language == "zh-CN" else english
        return template.format(**kwargs)
