from __future__ import annotations

from bilibili_tool.application import AppContext


class LibraryPage:
    """资源库页面，用于展示已经同步到本地的视频元数据。"""

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.table = None
        self.status_label = None
        self._table_item_class = None

    def build(self):
        """构造资源库表格，并提供手动刷新按钮。"""

        from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

        language = self.context.settings.ui_language
        self._table_item_class = QTableWidgetItem

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h3>资源库</h3>" if language == "zh-CN" else "<h3>Library</h3>"))
        layout.addWidget(
            QLabel(
                "这里展示已经写入本地数据库的视频。收藏夹同步成功后会立刻出现在这里。"
                if language == "zh-CN"
                else "This page shows videos already written into the local database. Favorite sync results appear here immediately."
            )
        )

        refresh_button = QPushButton("刷新资源库" if language == "zh-CN" else "Refresh Library")
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        self.status_label = QLabel("准备就绪。" if language == "zh-CN" else "Ready.")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 5)
        headers = ["ID", "BV", "标题", "作者", "来源链接"] if language == "zh-CN" else ["ID", "BV", "Title", "Owner", "Source URL"]
        self.table.setHorizontalHeaderLabels(headers)
        layout.addWidget(self.table)

        self.refresh()
        return widget

    def refresh(self) -> None:
        """从数据库重新加载资源库表格。"""

        language = self.context.settings.ui_language
        videos = self.context.library_service.list_videos(limit=100)
        self.table.setRowCount(len(videos))
        table_item = self._table_item_class
        for row_index, video in enumerate(videos):
            self.table.setItem(row_index, 0, table_item(str(video.id)))
            self.table.setItem(row_index, 1, table_item(video.bvid))
            self.table.setItem(row_index, 2, table_item(video.title))
            self.table.setItem(row_index, 3, table_item(video.owner_name or "-"))
            self.table.setItem(row_index, 4, table_item(video.source_url or "-"))
        self.status_label.setText(
            f"当前资源库共有 {len(videos)} 条本地视频记录。"
            if language == "zh-CN"
            else f"The local library currently contains {len(videos)} video records."
        )
