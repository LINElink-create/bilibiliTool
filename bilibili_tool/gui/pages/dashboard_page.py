from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from bilibili_tool.application import AppContext
from bilibili_tool.domain.enums import DownloadStatus
from bilibili_tool.gui.theme import card_frame, page_root


class DashboardPage:
    """首页仪表盘，集中展示本地资源、下载队列、登录状态和快捷入口。"""

    def __init__(
        self,
        context: AppContext,
        *,
        on_new_source: Callable[[], None] | None = None,
        on_open_library: Callable[[], None] | None = None,
        on_open_downloads: Callable[[], None] | None = None,
    ) -> None:
        self.context = context
        self.on_new_source = on_new_source
        self.on_open_library = on_open_library
        self.on_open_downloads = on_open_downloads

    def build(self):
        """构造与主导航风格一致的首页仪表盘。"""

        from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

        language = self.context.settings.ui_language
        stats = self._load_stats()
        widget, layout = page_root()
        layout.setSpacing(12)

        hero = card_frame("dashboardHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(4)
        welcome = QLabel(self._text(language, "欢迎使用 bilibiliTool", "Welcome to bilibiliTool"))
        welcome.setObjectName("heroTitle")
        subtitle = QLabel(
            self._text(
                language,
                "高效管理你的 B 站来源，追踪下载队列并快速处理视频。",
                "Manage bilibili sources, track downloads, and process videos quickly.",
            )
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(welcome)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        overview = card_frame("dashboardSection")
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(14, 12, 14, 14)
        overview_layout.setSpacing(10)
        overview_title = QLabel(self._text(language, "今日概览", "Overview"))
        overview_title.setObjectName("sectionTitle")
        overview_layout.addWidget(overview_title)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(10)
        metrics.addWidget(
            self._metric_card(
                self._text(language, "来源数量", "Sources"),
                str(stats["source_count"]),
                self._text(language, f"启用中 {stats['enabled_source_count']}", f"Enabled {stats['enabled_source_count']}"),
            ),
            0,
            0,
        )
        metrics.addWidget(
            self._metric_card(
                self._text(language, "视频数量", "Videos"),
                str(stats["video_count"]),
                self._text(language, f"今日新增 +{stats['video_today_count']}", f"Today +{stats['video_today_count']}"),
            ),
            0,
            1,
        )
        metrics.addWidget(
            self._metric_card(
                self._text(language, "下载任务", "Downloads"),
                str(stats["download_count"]),
                self._text(
                    language,
                    f"下载中 {stats['running_download_count']} | 等待中 {stats['pending_download_count']}",
                    f"Running {stats['running_download_count']} | Pending {stats['pending_download_count']}",
                ),
            ),
            0,
            2,
        )
        metrics.addWidget(
            self._metric_card(
                self._text(language, "当前登录状态", "Login Status"),
                self._text(language, "已登录" if stats["is_logged_in"] else "未登录", "Signed in" if stats["is_logged_in"] else "Not signed in"),
                stats["session_name"] or self._text(language, "请先完成本地登录", "Complete local login first"),
                accent=True,
            ),
            0,
            3,
        )
        for column in range(4):
            metrics.setColumnStretch(column, 1)
        overview_layout.addLayout(metrics)
        layout.addWidget(overview)

        lower = QGridLayout()
        lower.setHorizontalSpacing(12)
        lower.setVerticalSpacing(12)

        quick = card_frame("dashboardSection")
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(14, 12, 14, 14)
        quick_layout.setSpacing(12)
        quick_title = QLabel(self._text(language, "快速开始", "Quick Start"))
        quick_title.setObjectName("sectionTitle")
        quick_layout.addWidget(quick_title)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(
            self._action_button(
                icon="+",
                title=self._text(language, "新建来源", "New Source"),
                subtitle=self._text(language, "添加 UP 主或收藏夹", "Add UP or favorite"),
                callback=self.on_new_source,
                primary=True,
            )
        )
        action_row.addWidget(
            self._action_button(
                icon="[]",
                title=self._text(language, "打开资源库", "Open Library"),
                subtitle=self._text(language, "浏览和管理资源", "Browse resources"),
                callback=self.on_open_library,
            )
        )
        action_row.addWidget(
            self._action_button(
                icon="v",
                title=self._text(language, "开始下载", "Start Download"),
                subtitle=self._text(language, "处理队列中的任务", "Process queued tasks"),
                callback=self.on_open_downloads,
            )
        )
        quick_layout.addLayout(action_row)
        quick_layout.addStretch(1)
        lower.addWidget(quick, 0, 0)

        activity = card_frame("dashboardSection")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(14, 12, 14, 14)
        activity_layout.setSpacing(8)
        activity_title = QLabel(self._text(language, "最近活动", "Recent Activity"))
        activity_title.setObjectName("sectionTitle")
        activity_layout.addWidget(activity_title)
        for item in self._recent_activity_items(language):
            activity_layout.addWidget(self._activity_row(item["kind"], item["text"], item["time"]))
        activity_layout.addStretch(1)
        lower.addWidget(activity, 0, 1)

        lower.setColumnStretch(0, 1)
        lower.setColumnStretch(1, 1)
        layout.addLayout(lower, 1)
        layout.addStretch(1)
        return widget

    def _load_stats(self) -> dict[str, object]:
        """从本地数据库读取首页所需数字，避免首页刷新时额外联网。"""

        sources = self.context.source_service.list_sources()
        videos = self.context.library_service.list_videos(limit=5000)
        downloads = self.context.download_service.list_tasks(limit=5000)
        login_state = self.context.auth_service.get_login_state()
        today = datetime.now().date()
        return {
            "source_count": len(sources),
            "enabled_source_count": sum(1 for source in sources if source.is_enabled),
            "video_count": len(videos),
            "video_today_count": sum(1 for video in videos if video.created_at is not None and video.created_at.date() == today),
            "download_count": len(downloads),
            "running_download_count": sum(1 for task in downloads if task.status is DownloadStatus.RUNNING),
            "pending_download_count": sum(1 for task in downloads if task.status is DownloadStatus.PENDING),
            "is_logged_in": login_state.is_logged_in,
            "session_name": login_state.session_name if login_state.is_logged_in else "",
        }

    def _metric_card(self, title: str, value: str, subtitle: str, *, accent: bool = False):
        """创建首页顶部的概览数字卡片。"""

        from PySide6.QtWidgets import QLabel, QVBoxLayout

        card = card_frame("dashboardMetric")
        if accent:
            card.setProperty("accent", "true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("metricDelta")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        return card

    def _action_button(self, *, icon: str, title: str, subtitle: str, callback, primary: bool = False):
        """创建快捷开始按钮；按钮内部保留说明文字，降低误点成本。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

        box = QFrame()
        box.setObjectName("quickActionPrimary" if primary else "quickAction")
        box.setCursor(Qt.PointingHandCursor)
        box.mousePressEvent = lambda event: callback() if callback is not None else None
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        icon_label = QLabel(icon)
        icon_label.setObjectName("quickActionIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("quickActionTitle")
        title_label.setAlignment(Qt.AlignCenter)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("quickActionSubtitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(icon_label, 0, Qt.AlignHCenter)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return box

    def _activity_row(self, kind: str, text: str, time_text: str):
        """创建最近活动的一行，左侧圆点表示活动类型。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

        row = QFrame()
        row.setObjectName("activityRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        dot = QLabel(self._activity_symbol(kind))
        dot.setObjectName(f"activityDot_{kind}")
        dot.setAlignment(Qt.AlignCenter)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        text_label = QLabel(text)
        text_label.setObjectName("activityText")
        text_label.setWordWrap(True)
        text_box.addWidget(text_label)
        layout.addWidget(dot)
        layout.addLayout(text_box, 1)
        time_label = QLabel(time_text)
        time_label.setObjectName("activityTime")
        layout.addWidget(time_label, 0, Qt.AlignTop)
        return row

    def _recent_activity_items(self, language: str) -> list[dict[str, str]]:
        """汇总最近来源同步和下载记录，全部来自本地数据库。"""

        items: list[tuple[datetime | None, dict[str, str]]] = []
        for source in self.context.source_service.list_sources()[:5]:
            when = source.last_sync_at or source.updated_at or source.created_at
            source_type = self._text(language, "来源同步", "Source")
            if source.last_sync_at is None:
                source_type = self._text(language, "来源更新", "Source")
            items.append(
                (
                    when,
                    {
                        "kind": "source",
                        "text": f"{source_type}：{source.display_name}",
                        "time": self._format_time(when, language),
                    },
                )
            )

        for task in self.context.download_service.list_tasks(limit=5):
            when = task.updated_at or task.created_at
            items.append(
                (
                    when,
                    {
                        "kind": "download" if task.status is DownloadStatus.SUCCESS else "warning",
                        "text": self._text(language, f"下载{self._status_text(task.status.value)}：{task.display_name}", f"Download {task.status.value}: {task.display_name}"),
                        "time": self._format_time(when, language),
                    },
                )
            )

        items.sort(key=lambda pair: pair[0] or datetime.min, reverse=True)
        if not items:
            return [
                {
                    "kind": "source",
                    "text": self._text(language, "还没有活动，先新建一个来源吧。", "No activity yet. Create a source first."),
                    "time": "--",
                }
            ]
        return [item for _, item in items[:6]]

    def _status_text(self, status: str) -> str:
        """把下载状态转成首页最近活动里更自然的中文短语。"""

        return {
            "pending": "已入队",
            "running": "中",
            "success": "完成",
            "failed": "失败",
            "paused": "暂停",
            "canceled": "取消",
        }.get(status, status)

    def _activity_symbol(self, kind: str) -> str:
        """用 ASCII 短符号表示活动类型，避免依赖系统彩色图标字体。"""

        return {
            "source": "S",
            "download": "D",
            "warning": "!",
        }.get(kind, "i")

    def _format_time(self, value: datetime | None, language: str) -> str:
        """把时间压缩成首页右侧的小标签。"""

        if value is None:
            return self._text(language, "未知", "Unknown")
        return value.strftime("%H:%M")

    @staticmethod
    def _text(language: str, zh: str, en: str) -> str:
        """返回当前界面语言对应文案。"""

        return zh if language == "zh-CN" else en
