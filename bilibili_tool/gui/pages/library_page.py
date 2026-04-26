from __future__ import annotations

from datetime import datetime

from bilibili_tool.application import AppContext
from bilibili_tool.domain import SourceKind, SourceRecord, VideoRecord
from bilibili_tool.gui.pages.downloads_page import DownloadsPage
from bilibili_tool.gui.theme import page_root


class LibraryPage:
    """资源库页面，用左侧来源文件夹和右侧视频表格组织本地视频。"""

    SOURCE_ID_ROLE = 256

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.table = None
        self.source_list = None
        self.search_input = None
        self.status_label = None
        self._message_box_class = None
        self._input_dialog_class = None
        self._table_item_class = None
        self._list_item_class = None
        self._current_source_id: int | None = None
        self._sources: list[SourceRecord] = []
        self._visible_videos: list[VideoRecord] = []

    def build(self):
        """构造资源库页面，并提供来源筛选、搜索和下载入队操作。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QFrame,
            QHeaderView,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QInputDialog,
            QPushButton,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        self._message_box_class = QMessageBox
        self._input_dialog_class = QInputDialog
        self._table_item_class = QTableWidgetItem
        self._list_item_class = QListWidgetItem

        widget, root_layout = page_root()

        title = QLabel(self._text("资源库", "Library"))
        title.setObjectName("pageTitle")
        subtitle = QLabel(self._text("按来源文件夹浏览本地视频，并把选中视频加入下载队列。", "Browse local videos by source folder and queue selected videos for download."))
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("draftInput")
        self.search_input.setPlaceholderText(self._text("搜索标题、BV号、作者", "Search title, BV, owner"))
        self.search_input.textChanged.connect(self._apply_current_filter)
        toolbar.addWidget(self.search_input, 1)

        refresh_button = QPushButton(self._text("刷新", "Refresh"))
        refresh_button.setObjectName("softButton")
        refresh_button.clicked.connect(self.refresh)
        queue_selected_button = QPushButton(self._text("加入下载队列", "Queue Selected"))
        queue_selected_button.setObjectName("primaryButton")
        queue_selected_button.clicked.connect(self._queue_selected_video)
        queue_all_button = QPushButton(self._text("全部入队", "Queue All"))
        queue_all_button.clicked.connect(self._queue_all_videos)

        toolbar.addWidget(refresh_button)
        toolbar.addWidget(queue_selected_button)
        toolbar.addWidget(queue_all_button)
        root_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sourceCard")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(8)
        sidebar_title = QLabel(self._text("来源文件夹", "Source Folders"))
        sidebar_title.setObjectName("sectionTitle")
        sidebar_layout.addWidget(sidebar_title)

        self.source_list = QListWidget()
        self.source_list.setUniformItemSizes(False)
        self.source_list.currentItemChanged.connect(self._handle_source_changed)
        self.source_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.source_list.customContextMenuRequested.connect(self._show_source_context_menu)
        sidebar_layout.addWidget(self.source_list, 1)
        splitter.addWidget(sidebar)

        content = QFrame()
        content.setObjectName("sourceCard")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(8)

        self.status_label = QLabel(self._text("准备就绪。", "Ready."))
        self.status_label.setObjectName("sectionTitle")
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            self._text(
                ["ID", "标题", "BV号", "作者", "发布时间"],
                ["ID", "Title", "BV", "Owner", "Published At"],
            )
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_video_context_menu)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        content_layout.addWidget(self.table, 1)
        splitter.addWidget(content)
        splitter.setSizes([180, 720])

        self.refresh()
        return widget

    def refresh(self) -> None:
        """重新读取来源和视频，并保持当前来源选择。"""

        previous_source_id = self._current_source_id
        self._sources = self.context.source_service.list_sources()
        self._populate_source_list(previous_source_id)
        self._apply_current_filter()

    def _populate_source_list(self, preferred_source_id: int | None) -> None:
        """刷新左侧来源列表，把每个来源显示成一个文件夹入口。"""

        self.source_list.blockSignals(True)
        self.source_list.clear()

        all_count = len(self.context.library_service.list_videos(limit=5000))
        all_item = self._list_item_class(self._text(f"全部资源\n{all_count} 个视频", f"All Videos\n{all_count} videos"))
        all_item.setData(self.SOURCE_ID_ROLE, None)
        self.source_list.addItem(all_item)

        selected_row = 0
        for row_index, source in enumerate(self._sources, start=1):
            count = len(self.context.library_service.list_source_videos(source_id=source.id or 0, limit=5000))
            item = self._list_item_class(
                self._text(
                    f"{self._source_kind_label(source.kind)} · {source.display_name}\n{count} 个视频",
                    f"{self._source_kind_label(source.kind)} · {source.display_name}\n{count} videos",
                )
            )
            item.setToolTip(source.url)
            item.setData(self.SOURCE_ID_ROLE, source.id)
            self.source_list.addItem(item)
            if source.id == preferred_source_id:
                selected_row = row_index

        self.source_list.setCurrentRow(selected_row)
        self._current_source_id = self.source_list.currentItem().data(self.SOURCE_ID_ROLE)
        self.source_list.blockSignals(False)

    def _handle_source_changed(self, current, previous) -> None:
        """切换来源文件夹后刷新右侧视频表格。"""

        self._current_source_id = current.data(self.SOURCE_ID_ROLE) if current is not None else None
        self._apply_current_filter()

    def _apply_current_filter(self) -> None:
        """按当前来源和搜索词过滤视频。"""

        if self.table is None:
            return

        videos = self._load_current_scope_videos()
        keyword = (self.search_input.text() if self.search_input is not None else "").strip().lower()
        if keyword:
            videos = [
                video
                for video in videos
                if keyword in video.title.lower()
                or keyword in video.bvid.lower()
                or keyword in (video.owner_name or "").lower()
            ]

        self._visible_videos = videos
        self._populate_video_table(videos)
        self._update_status(len(videos))

    def _load_current_scope_videos(self) -> list[VideoRecord]:
        """读取当前左侧来源对应的视频列表。"""

        if self._current_source_id is None:
            return self.context.library_service.list_videos(limit=5000)
        return self.context.library_service.list_source_videos(source_id=self._current_source_id, limit=5000)

    def _populate_video_table(self, videos: list[VideoRecord]) -> None:
        """把当前范围的视频写入右侧表格。"""

        table_item = self._table_item_class
        self.table.setRowCount(len(videos))
        for row_index, video in enumerate(videos):
            values = [
                str(video.id),
                video.title,
                video.bvid,
                video.owner_name or "-",
                self._format_datetime(video.pub_time),
            ]
            for column_index, value in enumerate(values):
                item = table_item(value)
                item.setToolTip(value)
                self.table.setItem(row_index, column_index, item)

        self.table.resizeRowsToContents()

    def _queue_selected_video(self) -> None:
        """把右侧表格中选中的单个视频加入下载队列。"""

        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            message = self._text("请先选择一个视频。", "Select a video first.")
            self._message_box_class.warning(None, self._text("资源库", "Library"), message)
            return

        row_index = selected_ranges[0].topRow()
        item = self.table.item(row_index, 0)
        if item is None:
            return

        video = self.context.video_repository.get_by_id(int(item.text()))
        if video is None:
            return
        self._open_video_format_dialog(video)

    def _queue_all_videos(self) -> None:
        """把当前来源范围内的视频批量加入下载队列。"""

        if self._current_source_id is None:
            result = self.context.download_service.queue_library_videos(limit=500)
        else:
            result = self.context.download_service.queue_source_videos(source_id=self._current_source_id, limit=500)

        message = self._text(
            result.message,
            f"Queued {result.queued_count} task(s), skipped {result.skipped_count} existing task(s).",
        )
        self.status_label.setText(message)
        self._message_box_class.information(None, self._text("资源库", "Library"), message)

    def _show_source_context_menu(self, position) -> None:
        """显示左侧来源文件夹右键菜单。"""

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication, QMenu

        item = self.source_list.itemAt(position)
        if item is None:
            return
        self.source_list.setCurrentItem(item)
        source_id = item.data(self.SOURCE_ID_ROLE)
        source = self.context.source_repository.get_by_id(source_id) if source_id is not None else None

        menu = QMenu(self.source_list)
        queue_action = menu.addAction(self._text("加入该文件夹全部视频到下载队列", "Queue This Folder"))
        rename_action = menu.addAction(self._text("重命名来源", "Rename Source"))
        delete_action = menu.addAction(self._text("删除来源", "Delete Source"))
        menu.addSeparator()
        copy_action = menu.addAction(self._text("复制来源链接", "Copy Source URL"))
        open_action = menu.addAction(self._text("打开来源链接", "Open Source URL"))

        is_real_source = source is not None
        rename_action.setEnabled(is_real_source)
        delete_action.setEnabled(is_real_source)
        copy_action.setEnabled(is_real_source)
        open_action.setEnabled(is_real_source)

        selected = menu.exec(self.source_list.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected is queue_action:
            self._queue_all_videos()
            return
        if source is None:
            return
        if selected is rename_action:
            self._rename_source(source)
        elif selected is delete_action:
            self._delete_source(source)
        elif selected is copy_action:
            QApplication.clipboard().setText(source.url)
            self.status_label.setText(self._text("来源链接已复制。", "Source URL copied."))
        elif selected is open_action:
            QDesktopServices.openUrl(QUrl(source.url))

    def _show_video_context_menu(self, position) -> None:
        """显示右侧视频表格右键菜单。"""

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication, QMenu

        row_index = self.table.rowAt(position.y())
        if row_index < 0 or row_index >= len(self._visible_videos):
            return
        self.table.selectRow(row_index)
        video = self._visible_videos[row_index]
        video_url = video.source_url or f"https://www.bilibili.com/video/{video.bvid}"

        menu = QMenu(self.table)
        queue_action = menu.addAction(self._text("选择格式并下载", "Choose Formats and Queue"))
        copy_bv_action = menu.addAction(self._text("复制 BV号", "Copy BV"))
        copy_url_action = menu.addAction(self._text("复制视频链接", "Copy Video URL"))
        open_url_action = menu.addAction(self._text("打开视频链接", "Open Video URL"))
        menu.addSeparator()
        remove_action = menu.addAction(self._text("从当前来源移除", "Remove From Current Source"))
        remove_action.setEnabled(self._current_source_id is not None)

        selected = menu.exec(self.table.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected is queue_action:
            self._open_video_format_dialog(video)
        elif selected is copy_bv_action:
            QApplication.clipboard().setText(video.bvid)
            self.status_label.setText(self._text("BV号已复制。", "BV copied."))
        elif selected is copy_url_action:
            QApplication.clipboard().setText(video_url)
            self.status_label.setText(self._text("视频链接已复制。", "Video URL copied."))
        elif selected is open_url_action:
            QDesktopServices.openUrl(QUrl(video_url))
        elif selected is remove_action and self._current_source_id is not None and video.id is not None:
            self._remove_video_from_current_source(video)

    def _rename_source(self, source: SourceRecord) -> None:
        """重命名来源文件夹。"""

        new_name, accepted = self._input_dialog_class.getText(
            None,
            self._text("重命名来源", "Rename Source"),
            self._text("新的来源名称：", "New source name:"),
            text=source.display_name,
        )
        if not accepted:
            return
        try:
            updated = self.context.source_service.rename_source(source.id, new_name)
        except Exception as exc:
            self._message_box_class.warning(None, self._text("重命名来源", "Rename Source"), str(exc))
            return
        self.status_label.setText(self._text(f"来源已重命名为：{updated.display_name}", f"Source renamed to: {updated.display_name}"))
        self.refresh()

    def _delete_source(self, source: SourceRecord) -> None:
        """删除来源文件夹和它的本地关联。"""

        reply = self._message_box_class.question(
            None,
            self._text("删除来源", "Delete Source"),
            self._text(
                f"确定删除来源“{source.display_name}”吗？这不会删除已经下载到磁盘的文件。",
                f"Delete source \"{source.display_name}\"? Downloaded files on disk will not be deleted.",
            ),
        )
        if reply != self._message_box_class.Yes:
            return
        try:
            self.context.source_service.delete_source(source.id)
        except Exception as exc:
            self._message_box_class.warning(None, self._text("删除来源", "Delete Source"), str(exc))
            return
        self._current_source_id = None
        self.status_label.setText(self._text("来源已删除。", "Source deleted."))
        self.refresh()

    def _queue_video(self, video: VideoRecord) -> None:
        """把指定视频加入下载队列。"""

        if video.id is None:
            return
        task_id, created = self.context.download_service.queue_video_id(video.id, source_id=self._current_source_id)
        message = self._text(
            f"下载任务 #{task_id} 已加入队列。" if created else f"该视频已有下载任务 #{task_id}，已跳过重复入队。",
            f"Download task #{task_id} has been queued."
            if created
            else f"This video already has download task #{task_id}; duplicate queueing was skipped.",
        )
        self.status_label.setText(message)

    def _open_video_format_dialog(self, video: VideoRecord) -> None:
        """资源库单视频下载入口：先弹出格式选择，再把结果写入下载队列。"""

        if video.id is None:
            return
        helper = DownloadsPage(self.context)
        video_url = video.source_url or f"https://www.bilibili.com/video/{video.bvid}"
        helper._open_download_dialog(
            initial_value=video_url,
            initial_name=video.title,
            queue_video_id=video.id,
            source_id=self._current_source_id,
            auto_probe=True,
            on_done=self._handle_download_dialog_done,
        )

    def _handle_download_dialog_done(self, message: str) -> None:
        """格式选择弹窗完成后，刷新资源库状态文案。"""

        self.status_label.setText(message)

    def _remove_video_from_current_source(self, video: VideoRecord) -> None:
        """从当前来源移除视频关联。"""

        reply = self._message_box_class.question(
            None,
            self._text("从当前来源移除", "Remove From Current Source"),
            self._text(
                f"确定从当前来源移除“{video.title}”吗？视频元数据和已下载文件都会保留。",
                f"Remove \"{video.title}\" from the current source? Metadata and downloaded files will be kept.",
            ),
        )
        if reply != self._message_box_class.Yes:
            return
        self.context.library_service.unlink_video_from_source(self._current_source_id, video.id)
        self.status_label.setText(self._text("视频已从当前来源移除。", "Video removed from current source."))
        self._apply_current_filter()

    def _update_status(self, visible_count: int) -> None:
        """显示当前文件夹和过滤结果数量。"""

        current_item = self.source_list.currentItem() if self.source_list is not None else None
        source_name = current_item.text().splitlines()[0] if current_item is not None else self._text("全部资源", "All Videos")
        self.status_label.setText(
            self._text(
                f"当前文件夹：{source_name}，显示 {visible_count} 条视频。",
                f"Current folder: {source_name}, showing {visible_count} videos.",
            )
        )

    def _source_kind_label(self, kind: SourceKind) -> str:
        """把来源类型翻译成更像文件夹标签的短文本。"""

        if kind is SourceKind.USER:
            return self._text("UP", "UP")
        if kind is SourceKind.FAVORITE:
            return self._text("收藏夹", "Favorite")
        return self._text("视频", "Video")

    def _format_datetime(self, value: datetime | None) -> str:
        """把发布时间格式化成列表里容易扫读的文本。"""

        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M")

    def _text(self, zh, en):
        """根据当前 UI 语言返回对应文本。"""

        return zh if self.context.settings.ui_language == "zh-CN" else en
