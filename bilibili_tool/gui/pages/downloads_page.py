from __future__ import annotations

import threading
from pathlib import Path
from queue import Empty, SimpleQueue

from bilibili_tool.application import AppContext
from bilibili_tool.domain import SourceKind, VideoFormatOption, VideoFormatProbeResult
from bilibili_tool.gui.theme import card_frame, page_root


class DownloadsPage:
    """下载中心页面，负责单视频格式探测与下载。"""

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.value_input = None
        self.name_input = None
        self.manual_format_input = None
        self.status_label = None
        self.selection_summary_label = None
        self.tasks_table = None
        self.video_table = None
        self.audio_table = None
        self.video_combo = None
        self.audio_combo = None
        self.merge_checkbox = None
        self.formats_title_label = None
        self.total_tasks_label = None
        self.running_tasks_label = None
        self.pending_tasks_label = None
        self.success_tasks_label = None
        self._table_item_class = None
        self._message_box_class = None
        self._refresh_timer = None
        self._active_threads: list[threading.Thread] = []
        self._ui_events: SimpleQueue[tuple[str, object]] = SimpleQueue()
        self._video_formats: tuple[VideoFormatOption, ...] = ()
        self._audio_formats: tuple[VideoFormatOption, ...] = ()
        self._dialog_queue_video_id: int | None = None
        self._dialog_source_id: int | None = None
        self._dialog_update_task_id: int | None = None
        self._dialog_done_callback = None
        self._dialog_completion_message: str | None = None

    def build(self):
        """构造下载页面，把探测、选择和下载放到同一处。"""

        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        ffmpeg_status = self.context.download_service.get_ffmpeg_status()
        self._message_box_class = QMessageBox
        self._table_item_class = QTableWidgetItem

        widget, layout = page_root()

        title_label = QLabel(self._text("下载中心", "Downloads"))
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)

        downloads_hint = QLabel(
            self._text(
                f"下载目录：{self.context.paths.downloads_dir}",
                f"Downloads directory: {self.context.paths.downloads_dir}",
            )
        )
        downloads_hint.setObjectName("pageSubtitle")
        downloads_hint.setWordWrap(True)
        layout.addWidget(downloads_hint)

        overview_row = QHBoxLayout()
        overview_row.setSpacing(12)
        self.total_tasks_label = self._build_summary_card(self._text("总任务", "Total"), "0")
        self.running_tasks_label = self._build_summary_card(self._text("下载中", "Running"), "0")
        self.pending_tasks_label = self._build_summary_card(self._text("等待中", "Pending"), "0")
        self.success_tasks_label = self._build_summary_card(self._text("已完成", "Done"), "0")
        for card in (self.total_tasks_label, self.running_tasks_label, self.pending_tasks_label, self.success_tasks_label):
            overview_row.addWidget(card, 1)
        layout.addLayout(overview_row)

        self.status_label = QLabel(self._text("准备就绪。", "Ready."))
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)

        tasks_group = card_frame()
        tasks_layout = QVBoxLayout(tasks_group)
        tasks_layout.setContentsMargins(14, 12, 14, 12)
        tasks_title = QLabel(self._text("当前任务", "Current Tasks"))
        tasks_title.setObjectName("sectionTitle")
        tasks_layout.addWidget(tasks_title)

        self.tasks_table = QTableWidget(0, 5)
        self.tasks_table.setHorizontalHeaderLabels(
            self._text(
                ["状态", "标题", "格式", "进度", "保存位置"],
                ["Status", "Title", "Format", "Progress", "Save Path"],
            )
        )
        self._configure_table(self.tasks_table, header_stretch_column=1)
        self._configure_task_queue_table()
        self.tasks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tasks_table.customContextMenuRequested.connect(self._show_task_context_menu)
        tasks_layout.addWidget(self.tasks_table, 1)

        queue_buttons = QHBoxLayout()
        new_download_button = QPushButton(self._text("新建下载", "New Download"))
        new_download_button.setObjectName("primaryButton")
        new_download_button.clicked.connect(self._open_download_dialog)
        run_next_button = QPushButton(self._text("开始队列", "Start Queue"))
        run_next_button.setObjectName("primaryButton")
        run_next_button.clicked.connect(self._start_run_next_task)
        pause_button = QPushButton(self._text("取消任务", "Cancel Task"))
        pause_button.clicked.connect(self._cancel_selected_task)
        retry_button = QPushButton(self._text("重试失败", "Retry Failed"))
        retry_button.clicked.connect(self._retry_selected_task)
        open_dir_button = QPushButton(self._text("打开目录", "Open Folder"))
        open_dir_button.clicked.connect(self._open_downloads_dir)
        refresh_button = QPushButton(self._text("刷新", "Refresh"))
        refresh_button.clicked.connect(self.refresh)
        for button in (new_download_button, run_next_button, pause_button, retry_button, open_dir_button, refresh_button):
            queue_buttons.addWidget(button)
        queue_buttons.addStretch(1)
        tasks_layout.addLayout(queue_buttons)
        tasks_layout.addWidget(self.status_label)
        layout.addWidget(tasks_group)

        if self.tasks_table is None:
            return
        self._refresh_tasks_table()

        self._refresh_timer = QTimer(widget)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.refresh)
        return widget

    def on_page_shown(self) -> None:
        """下载页可见时才启动刷新，避免切到其他页面后继续重建表格。"""

        self.refresh()
        if self._refresh_timer is not None and not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def on_page_hidden(self) -> None:
        """离开下载页时暂停刷新定时器，减少顶部标签切换卡顿。"""

        if self._refresh_timer is not None and self._refresh_timer.isActive():
            self._refresh_timer.stop()

    def refresh(self) -> None:
        """刷新下载任务表格，并消费后台线程回传的事件。"""

        self._refresh_tasks_table()
        self._flush_ui_events()

    def _build_summary_card(self, title: str, value: str):
        """创建下载页顶部的队列统计卡片，并返回数值标签。"""

        from PySide6.QtWidgets import QLabel, QVBoxLayout

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card._value_label = value_label
        return card

    def _set_summary_value(self, card, value: int) -> None:
        """更新顶部统计卡片中的数字。"""

        label = getattr(card, "_value_label", None)
        if label is not None:
            label.setText(str(value))

    def _open_download_dialog(
        self,
        *,
        initial_value: str = "",
        initial_name: str = "",
        queue_video_id: int | None = None,
        source_id: int | None = None,
        update_task_id: int | None = None,
        auto_probe: bool = False,
        on_done=None,
    ) -> None:
        """打开新建下载弹窗，在弹窗里选择视频流和音频流方案。"""

        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDialog,
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTableWidget,
            QVBoxLayout,
        )

        previous_status_label = self.status_label
        self._dialog_queue_video_id = queue_video_id
        self._dialog_source_id = source_id
        self._dialog_update_task_id = update_task_id
        self._dialog_done_callback = on_done
        self._dialog_completion_message = None
        if self._message_box_class is None:
            from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

            self._message_box_class = QMessageBox
            self._table_item_class = QTableWidgetItem

        ffmpeg_status = self.context.download_service.get_ffmpeg_status()
        dialog = QDialog()
        dialog.setWindowTitle(self._text("选择下载格式", "Choose Download Formats"))
        dialog.setMinimumSize(1080, 720)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        input_group = QGroupBox(self._text("下载选项", "Download Options"))
        input_group.setObjectName("cardGroup")
        input_layout = QFormLayout(input_group)
        input_layout.setSpacing(10)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText(self._text("输入 BV 号或 B 站视频链接", "Enter a BV id or bilibili video URL"))
        self.value_input.setText(initial_value)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self._text("可选显示名称，不填时默认使用解析结果", "Optional display name"))
        self.name_input.setText(initial_name)
        self.name_input.textChanged.connect(self._update_selection_summary)
        self.manual_format_input = QLineEdit()
        self.manual_format_input.setPlaceholderText(self._text("可选：手动填写 yt-dlp 格式选择器", "Optional yt-dlp format selector"))
        if update_task_id is not None:
            task = self.context.download_task_repository.get_by_id(update_task_id)
            if task is not None and task.format_selector != self.context.download_service.DEFAULT_FORMAT_SELECTOR:
                self.manual_format_input.setText(task.format_selector)
        self.manual_format_input.textChanged.connect(self._update_selection_summary)

        inspect_button = QPushButton(self._text("探测格式", "Inspect Formats"))
        inspect_button.setObjectName("softButton")
        inspect_button.clicked.connect(self._start_format_probe)
        start_button = QPushButton(self._text("保存到队列", "Save to Queue"))
        start_button.setObjectName("primaryButton")
        start_button.clicked.connect(self._confirm_download_dialog)
        close_button = QPushButton(self._text("关闭", "Close"))
        close_button.clicked.connect(dialog.reject)
        button_row = QHBoxLayout()
        button_row.addWidget(inspect_button)
        button_row.addWidget(start_button)
        button_row.addWidget(close_button)
        button_row.addStretch(1)

        self.status_label = QLabel(self._text("准备就绪。", "Ready."))
        self.status_label.setWordWrap(True)
        input_layout.addRow(self._text("输入值", "Value"), self.value_input)
        input_layout.addRow(self._text("显示名称", "Display Name"), self.name_input)
        input_layout.addRow(self._text("格式覆盖", "Format Override"), self.manual_format_input)
        input_layout.addRow(button_row)
        input_layout.addRow(self._text("状态", "Status"), self.status_label)
        layout.addWidget(input_group)

        self.formats_title_label = QLabel(self._text("<b>当前格式结果：</b> 还没有进行探测。", "<b>Current formats:</b> nothing has been inspected yet."))
        self.formats_title_label.setWordWrap(True)
        layout.addWidget(self.formats_title_label)

        format_row = QHBoxLayout()
        format_row.setSpacing(12)
        video_group = QGroupBox(self._text("视频流", "Video Streams"))
        video_group.setObjectName("cardGroup")
        video_layout = QVBoxLayout(video_group)
        self.video_table = QTableWidget(0, 5)
        self.video_table.setHorizontalHeaderLabels(self._text(["格式ID", "清晰度", "说明", "视频编码", "大小"], ["Format ID", "Quality", "Label", "Video Codec", "Size"]))
        self._configure_table(self.video_table, header_stretch_column=2)
        self.video_table.itemSelectionChanged.connect(self._handle_video_table_selection)
        self.video_combo = QComboBox()
        self.video_combo.currentIndexChanged.connect(self._handle_video_combo_selection)
        video_layout.addWidget(self.video_table)
        video_layout.addWidget(QLabel(self._text("选择视频格式", "Select video format")))
        video_layout.addWidget(self.video_combo)
        format_row.addWidget(video_group, 1)

        audio_group = QGroupBox(self._text("音频流", "Audio Streams"))
        audio_group.setObjectName("cardGroup")
        audio_layout = QVBoxLayout(audio_group)
        self.audio_table = QTableWidget(0, 5)
        self.audio_table.setHorizontalHeaderLabels(self._text(["格式ID", "音频类型", "说明", "音频编码", "大小"], ["Format ID", "Audio Type", "Label", "Audio Codec", "Size"]))
        self._configure_table(self.audio_table, header_stretch_column=2)
        self.audio_table.itemSelectionChanged.connect(self._handle_audio_table_selection)
        self.audio_combo = QComboBox()
        self.audio_combo.currentIndexChanged.connect(self._handle_audio_combo_selection)
        audio_layout.addWidget(self.audio_table)
        audio_layout.addWidget(QLabel(self._text("选择音频格式", "Select audio format")))
        audio_layout.addWidget(self.audio_combo)
        format_row.addWidget(audio_group, 1)
        layout.addLayout(format_row, 1)

        options_group = QGroupBox(self._text("输出方案", "Output Plan"))
        options_group.setObjectName("cardGroup")
        options_layout = QFormLayout(options_group)
        self.merge_checkbox = QCheckBox(self._text("合并音视频为单个文件", "Merge video and audio into one file"))
        self.merge_checkbox.setChecked(ffmpeg_status.available)
        self.merge_checkbox.setEnabled(ffmpeg_status.available)
        if not ffmpeg_status.available:
            self.merge_checkbox.setToolTip(self._text("当前环境没有 ffmpeg，所以只能分开下载音视频。", "ffmpeg is not available, so streams can only be downloaded separately."))
        self.merge_checkbox.toggled.connect(self._update_selection_summary)
        self.selection_summary_label = QLabel(self._text("下载计划：默认使用自动选择。", "Plan: the default automatic selector will be used."))
        self.selection_summary_label.setWordWrap(True)
        options_layout.addRow(self._text("合并选项", "Merge Option"), self.merge_checkbox)
        options_layout.addRow(self._text("下载计划", "Download Plan"), self.selection_summary_label)
        layout.addWidget(options_group)

        self._video_formats = ()
        self._audio_formats = ()
        self._populate_format_controls(())
        self._update_selection_summary()
        self.value_input.setFocus()
        dialog_timer = QTimer(dialog)
        dialog_timer.setInterval(300)
        dialog_timer.timeout.connect(self._flush_ui_events)
        dialog_timer.start()
        if auto_probe and initial_value:
            self._start_format_probe()
        try:
            dialog.exec()
        finally:
            dialog_timer.stop()
            self.status_label = previous_status_label
            if previous_status_label is not None and self._dialog_completion_message:
                previous_status_label.setText(self._dialog_completion_message)
            self.value_input = None
            self.name_input = None
            self.manual_format_input = None
            self.selection_summary_label = None
            self.video_table = None
            self.audio_table = None
            self.video_combo = None
            self.audio_combo = None
            self.merge_checkbox = None
            self.formats_title_label = None
            self._dialog_queue_video_id = None
            self._dialog_source_id = None
            self._dialog_update_task_id = None
            self._dialog_done_callback = None
            self._dialog_completion_message = None
            if self.tasks_table is not None:
                self.refresh()

    def _open_downloads_dir(self) -> None:
        """打开默认下载目录。"""

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.downloads_dir)))

    def _start_format_probe(self) -> None:
        """后台探测当前视频可用格式，避免界面在网络请求期间卡住。"""

        raw_value = self.value_input.text().strip()
        if not raw_value:
            message = self._text("请先输入 BV 号或视频链接。", "Enter a BV id or video URL first.")
            self.status_label.setText(message)
            self._show_feedback(self._text("查看可用格式", "Inspect Formats"), message, level="warning")
            return

        self.status_label.setText(self._text("正在探测可用格式，请稍候。", "Inspecting available formats, please wait."))
        self._start_background_thread(target=self._run_format_probe, args=(raw_value,))

    def _confirm_download_dialog(self) -> None:
        """把弹窗里选择的格式保存到下载队列，而不是绕过队列立即下载。"""

        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None
        if not raw_value:
            message = self._text("请先输入 BV 号或视频链接。", "Enter a BV id or video URL first.")
            self.status_label.setText(message)
            self._show_feedback(self._text("保存到队列", "Save to Queue"), message, level="warning")
            return

        try:
            if self._dialog_update_task_id is not None:
                message = self._save_format_to_existing_task(display_name)
            elif self._dialog_queue_video_id is not None:
                message = self._queue_library_video_with_selected_format(raw_value, display_name)
            else:
                message = self._queue_manual_video_with_selected_format(raw_value, display_name)
        except Exception as exc:
            self._show_feedback(self._text("保存到队列", "Save to Queue"), str(exc), level="warning")
            return

        self.status_label.setText(message)
        self._dialog_completion_message = message
        callback = self._dialog_done_callback
        if callback is not None:
            callback(message)
        self._show_feedback(self._text("保存到队列", "Save to Queue"), message)
        window = self.value_input.window()
        if hasattr(window, "accept"):
            window.accept()

    def _save_format_to_existing_task(self, display_name: str | None) -> str:
        """右键“重新选择格式”时，只更新当前任务的 format_selector。"""

        task = self.context.download_task_repository.get_by_id(self._dialog_update_task_id)
        if task is None or task.id is None:
            raise ValueError(self._text("下载任务不存在。", "Download task was not found."))

        plan = self._build_download_plan(display_name or task.display_name)
        if len(plan) != 1:
            raise ValueError(
                self._text(
                    "已有任务只能保存一个格式选择器；请启用合并音视频，或只选择一个视频/音频流。",
                    "Existing tasks can only keep one format selector; enable merge or select one stream.",
                )
            )

        updated = self.context.download_service.update_task_format(task.id, plan[0][1])
        return self._text(
            f"任务 #{updated.id} 的格式已更新为 {updated.format_selector}。",
            f"Task #{updated.id} format was updated to {updated.format_selector}.",
        )

    def _queue_library_video_with_selected_format(self, raw_value: str, display_name: str | None) -> str:
        """资源库单视频入口：先选格式，再把任务加入对应来源文件夹的下载队列。"""

        video = self.context.video_repository.get_by_id(self._dialog_queue_video_id)
        if video is None:
            raise ValueError(self._text("资源库视频不存在。", "Library video was not found."))

        resolved_name = display_name or video.title
        resolved_url = video.source_url or raw_value
        plan = self._build_download_plan(resolved_name)
        if len(plan) == 1:
            task_id, created = self.context.download_service.queue_video_id(
                video.id,
                format_selector=plan[0][1],
                source_id=self._dialog_source_id,
            )
            if not created and task_id is not None:
                updated = self.context.download_service.update_task_format(task_id, plan[0][1])
                return self._text(
                    f"该视频已有任务 #{updated.id}，已更新格式为 {updated.format_selector}。",
                    f"Existing task #{updated.id} was updated to {updated.format_selector}.",
                )
            return self._text(f"下载任务 #{task_id} 已加入队列。", f"Download task #{task_id} has been queued.")

        target_dir = self.context.download_service.target_dir_for_source_id(self._dialog_source_id)
        task_ids = [
            self.context.download_service.queue_url(
                url=resolved_url,
                display_name=task_name,
                format_selector=format_selector,
                video_id=video.id,
                target_dir=target_dir,
            )
            for task_name, format_selector in plan
        ]
        return self._text(
            f"已按音视频分离方案加入 {len(task_ids)} 个下载任务。",
            f"Queued {len(task_ids)} split stream download tasks.",
        )

    def _queue_manual_video_with_selected_format(self, raw_value: str, display_name: str | None) -> str:
        """下载页新建入口：解析输入并把选择好的格式写入队列。"""

        preview = self.context.source_service.preview_source(
            kind=SourceKind.VIDEO,
            raw_value=raw_value,
            display_name=display_name,
        )
        resolved_url = preview.canonical_url or raw_value
        resolved_name = display_name or preview.display_name
        plan = self._build_download_plan(resolved_name)
        task_ids = [
            self.context.download_service.queue_url(
                url=resolved_url,
                display_name=task_name,
                format_selector=format_selector,
            )
            for task_name, format_selector in plan
        ]
        return self._text(
            f"已加入 {len(task_ids)} 个下载任务，请在队列中点击开始。",
            f"Queued {len(task_ids)} download task(s); use Start Queue to run them.",
        )

    def _start_single_video_download(self) -> None:
        """解析单视频输入，并在后台线程里执行真实下载。"""

        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        if not raw_value:
            message = self._text("请先输入 BV 号或视频链接。", "Enter a BV id or video URL first.")
            self.status_label.setText(message)
            self._show_feedback(self._text("开始下载", "Start Download"), message, level="warning")
            return

        try:
            preview = self.context.source_service.preview_source(
                kind=SourceKind.VIDEO,
                raw_value=raw_value,
                display_name=display_name,
            )
        except ValueError as exc:
            message = self._text(f"下载前解析失败：{exc}", f"Download preview failed: {exc}")
            self.status_label.setText(message)
            self._show_feedback(self._text("开始下载", "Start Download"), message, level="warning")
            return

        resolved_url = preview.canonical_url or raw_value
        resolved_name = display_name or preview.display_name
        download_plan = self._build_download_plan(resolved_name)
        self.status_label.setText(self._describe_download_plan(download_plan))
        self._start_background_thread(target=self._run_download_plan, args=(resolved_url, download_plan))

    def _start_background_thread(self, *, target, args: tuple[object, ...]) -> None:
        """统一管理后台线程，避免下载和探测各自维护一套启动逻辑。"""

        # 所有耗时操作都走后台线程，主线程只负责表格和提示更新，避免按钮假死。
        worker = threading.Thread(target=target, args=args, daemon=True)
        self._active_threads.append(worker)
        worker.start()

    def _run_format_probe(self, raw_value: str) -> None:
        """后台线程里执行真实格式探测，并把结果投递回 UI 线程。"""

        try:
            result = self.context.download_service.probe_video_formats(raw_value=raw_value)
        except Exception as exc:
            message = self._text(f"格式探测失败：{exc}", f"Format probe failed: {exc}")
            self._ui_events.put(("message", ("error", message)))
            return

        self._ui_events.put(("formats", result))
        summary = self._text(
            f"已获取 {len(result.formats)} 个可用格式。",
            f"Loaded {len(result.formats)} available formats.",
        )
        self._ui_events.put(("message", ("info", summary)))

    def _run_download_plan(self, url: str, download_plan: tuple[tuple[str, str], ...]) -> None:
        """后台线程里按计划执行一个或多个下载任务，并汇总结果。"""

        completed_tasks = []
        failures = []
        for display_name, format_selector in download_plan:
            try:
                task = self.context.download_service.download_now(
                    url=url,
                    display_name=display_name,
                    format_selector=format_selector,
                )
            except Exception as exc:
                failures.append((display_name, str(exc)))
                continue

            completed_tasks.append(task)
            if task.status.value != "success":
                failures.append(
                    (
                        display_name,
                        task.error_message or self._text("下载未成功完成。", "The download did not finish successfully."),
                    )
                )

        if failures:
            lines = [self._text("以下任务执行失败：", "The following tasks failed:")]
            for display_name, error_message in failures:
                lines.append(f"- {display_name}: {error_message}")
            if completed_tasks:
                lines.append(self._text("已完成的任务：", "Completed tasks:"))
                for task in completed_tasks:
                    if task.status.value == "success":
                        lines.append(f"- {task.display_name}: {task.file_path or '-'}")
            self._ui_events.put(("message", ("error", "\n".join(lines))))
            return

        lines = [self._text("下载完成：", "Download finished:")]
        for task in completed_tasks:
            lines.append(f"- {task.display_name}: {task.file_path or '-'}")
        self._ui_events.put(("message", ("info", "\n".join(lines))))

    def _start_run_next_task(self) -> None:
        """后台执行队列里的下一个 pending 下载。"""

        self.status_label.setText(self._text("正在运行下一个下载任务。", "Running the next download task."))
        self._start_background_thread(target=self._run_next_task, args=())

    def _run_next_task(self) -> None:
        """执行一个 pending 任务并把结果回传 UI。"""

        try:
            task = self.context.download_service.run_next()
        except Exception as exc:
            self._ui_events.put(("message", ("error", self._text(f"运行队列失败：{exc}", f"Queue run failed: {exc}"))))
            return

        if task is None:
            self._ui_events.put(("message", ("info", self._text("没有待运行的下载任务。", "No pending download tasks."))))
            return
        message = self._text(
            f"任务 #{task.id} 结束：{task.status.value}。",
            f"Task #{task.id} finished: {task.status.value}.",
        )
        self._ui_events.put(("message", ("info" if task.status.value == "success" else "error", message)))

    def _start_run_task(self, task_id: int) -> None:
        """后台运行右键选中的下载任务。"""

        self.status_label.setText(self._text(f"正在运行任务 #{task_id}。", f"Running task #{task_id}."))
        self._start_background_thread(target=self._run_specific_task, args=(task_id,))

    def _run_specific_task(self, task_id: int) -> None:
        """执行一个指定任务并把结果回传 UI。"""

        try:
            task = self.context.download_service.run_task(task_id)
        except Exception as exc:
            self._ui_events.put(("message", ("error", self._text(f"运行任务失败：{exc}", f"Task run failed: {exc}"))))
            return
        message = self._text(
            f"任务 #{task.id} 结束：{task.status.value}。",
            f"Task #{task.id} finished: {task.status.value}.",
        )
        self._ui_events.put(("message", ("info" if task.status.value == "success" else "error", message)))

    def _retry_selected_task(self) -> None:
        """重试选中的失败任务。"""

        task_id = self._selected_task_id()
        if task_id is None:
            return
        try:
            task = self.context.download_service.retry_task(task_id)
        except Exception as exc:
            self._show_feedback(self._text("重试选中", "Retry Selected"), str(exc), level="warning")
            return
        self.status_label.setText(self._text(f"任务 #{task.id} 已重置为 pending。", f"Task #{task.id} was reset to pending."))
        self.refresh()

    def _pause_selected_task(self) -> None:
        """暂停选中的 pending 任务。"""

        self._change_selected_task_state("pause")

    def _resume_selected_task(self) -> None:
        """恢复选中的 paused 任务。"""

        self._change_selected_task_state("resume")

    def _cancel_selected_task(self) -> None:
        """取消选中的队列任务。"""

        self._change_selected_task_state("cancel")

    def _change_selected_task_state(self, action: str) -> None:
        """执行轻量队列状态切换。"""

        task_id = self._selected_task_id()
        if task_id is None:
            return
        title = {
            "pause": self._text("暂停选中", "Pause Selected"),
            "resume": self._text("恢复选中", "Resume Selected"),
            "cancel": self._text("取消选中", "Cancel Selected"),
        }[action]
        try:
            if action == "pause":
                task = self.context.download_service.pause_task(task_id)
            elif action == "resume":
                task = self.context.download_service.resume_task(task_id)
            else:
                task = self.context.download_service.cancel_task(task_id)
        except Exception as exc:
            self._show_feedback(title, str(exc), level="warning")
            return

        self.status_label.setText(
            self._text(f"任务 #{task.id} 当前状态：{task.status.value}。", f"Task #{task.id} status: {task.status.value}.")
        )
        self.refresh()

    def _selected_task_id(self) -> int | None:
        """读取下载任务表格当前选中的任务 ID。"""

        selected_ranges = self.tasks_table.selectedRanges()
        if not selected_ranges:
            message = self._text("请先选择一个下载任务。", "Select a download task first.")
            self._show_feedback(self._text("下载任务", "Download Tasks"), message, level="warning")
            return None
        item = self.tasks_table.item(selected_ranges[0].topRow(), 0)
        if item is None:
            return None
        task_id = item.data(256)
        return int(task_id) if task_id is not None else None

    def _show_task_context_menu(self, position) -> None:
        """显示下载任务表右键菜单。"""

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication, QMenu

        row_index = self.tasks_table.rowAt(position.y())
        if row_index < 0:
            return
        self.tasks_table.selectRow(row_index)
        task = self._task_for_row(row_index)
        if task is None or task.id is None:
            return

        menu = QMenu(self.tasks_table)
        run_action = menu.addAction(self._text("运行任务", "Run Task"))
        retry_action = menu.addAction(self._text("重试任务", "Retry Task"))
        pause_action = menu.addAction(self._text("暂停任务", "Pause Task"))
        resume_action = menu.addAction(self._text("恢复任务", "Resume Task"))
        cancel_action = menu.addAction(self._text("取消任务", "Cancel Task"))
        format_action = menu.addAction(self._text("重新选择格式", "Choose Formats Again"))
        menu.addSeparator()
        copy_path_action = menu.addAction(self._text("复制文件路径", "Copy File Path"))
        open_folder_action = menu.addAction(self._text("打开所在文件夹", "Open Containing Folder"))
        copy_url_action = menu.addAction(self._text("复制来源链接", "Copy Source URL"))
        menu.addSeparator()
        delete_action = menu.addAction(self._text("删除任务记录", "Delete Task Record"))

        status = task.status.value
        run_action.setEnabled(status in {"pending", "failed"})
        retry_action.setEnabled(status == "failed")
        pause_action.setEnabled(status == "pending")
        resume_action.setEnabled(status == "paused")
        cancel_action.setEnabled(status in {"pending", "running", "paused", "failed"})
        format_action.setEnabled(status not in {"running", "success"})
        copy_path_action.setEnabled(bool(task.file_path))
        open_folder_action.setEnabled(bool(task.file_path or task.target_dir))
        delete_action.setEnabled(status != "running")

        selected = menu.exec(self.tasks_table.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected is run_action:
            self._start_run_task(task.id)
        elif selected is retry_action:
            self._change_task_state_by_id(task.id, "retry")
        elif selected is pause_action:
            self._change_task_state_by_id(task.id, "pause")
        elif selected is resume_action:
            self._change_task_state_by_id(task.id, "resume")
        elif selected is cancel_action:
            self._change_task_state_by_id(task.id, "cancel")
        elif selected is format_action:
            self._open_download_dialog(
                initial_value=task.source_url,
                initial_name=task.display_name,
                update_task_id=task.id,
                auto_probe=True,
            )
        elif selected is copy_path_action and task.file_path:
            QApplication.clipboard().setText(task.file_path)
            self.status_label.setText(self._text("文件路径已复制。", "File path copied."))
        elif selected is open_folder_action:
            folder_path = Path(task.file_path).parent if task.file_path else Path(task.target_dir or ".")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_path)))
        elif selected is copy_url_action:
            QApplication.clipboard().setText(task.source_url)
            self.status_label.setText(self._text("来源链接已复制。", "Source URL copied."))
        elif selected is delete_action:
            self._delete_task_record(task.id)

    def _task_for_row(self, row_index: int):
        """按表格行读取对应下载任务。"""

        item = self.tasks_table.item(row_index, 0)
        if item is None:
            return None
        task_id = item.data(256)
        if task_id is None:
            return None
        return self.context.download_task_repository.get_by_id(int(task_id))

    def _change_task_state_by_id(self, task_id: int, action: str) -> None:
        """右键菜单入口使用的任务状态切换。"""

        try:
            if action == "retry":
                task = self.context.download_service.retry_task(task_id)
            elif action == "pause":
                task = self.context.download_service.pause_task(task_id)
            elif action == "resume":
                task = self.context.download_service.resume_task(task_id)
            else:
                task = self.context.download_service.cancel_task(task_id)
        except Exception as exc:
            self._show_feedback(self._text("下载任务", "Download Task"), str(exc), level="warning")
            return
        self.status_label.setText(
            self._text(f"任务 #{task.id} 当前状态：{task.status.value}。", f"Task #{task.id} status: {task.status.value}.")
        )
        self.refresh()

    def _delete_task_record(self, task_id: int) -> None:
        """删除下载任务记录，但不删除磁盘文件。"""

        reply = self._message_box_class.question(
            None,
            self._text("删除任务记录", "Delete Task Record"),
            self._text(
                f"确定删除下载任务 #{task_id} 的记录吗？这不会删除磁盘文件。",
                f"Delete download task #{task_id}? Files on disk will not be deleted.",
            ),
        )
        if reply != self._message_box_class.Yes:
            return
        try:
            self.context.download_service.delete_task_record(task_id)
        except Exception as exc:
            self._show_feedback(self._text("删除任务记录", "Delete Task Record"), str(exc), level="warning")
            return
        self.status_label.setText(self._text("任务记录已删除。", "Task record deleted."))
        self.refresh()

    def _refresh_tasks_table(self) -> None:
        """把数据库里的下载任务刷新到页面表格里。"""

        from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QWidget

        tasks = self.context.download_service.list_tasks(limit=100)
        table_item = self._table_item_class
        status_counts = {"running": 0, "pending": 0, "success": 0}
        self.tasks_table.setRowCount(len(tasks))
        for row_index, task in enumerate(tasks):
            status = task.status.value
            if status in status_counts:
                status_counts[status] += 1
            status_item = table_item(self._status_label(status))
            status_item.setData(256, task.id)
            self.tasks_table.setItem(row_index, 0, status_item)
            self.tasks_table.setItem(row_index, 1, table_item(task.display_name))
            self.tasks_table.setItem(row_index, 2, table_item(task.format_selector))
            progress = QProgressBar()
            progress.setObjectName("downloadTaskProgress")
            progress.setRange(0, 100)
            progress.setValue(int(task.progress))
            progress.setFormat(f"{task.progress:.0f}%")
            progress.setMinimumHeight(20)
            progress.setMaximumHeight(20)
            progress_box = QWidget()
            progress_layout = QHBoxLayout(progress_box)
            progress_layout.setContentsMargins(10, 5, 10, 5)
            progress_layout.setSpacing(0)
            progress_layout.addWidget(progress)
            self.tasks_table.setCellWidget(row_index, 3, progress_box)
            self.tasks_table.setItem(row_index, 4, table_item(task.file_path or task.target_dir or "-"))
            self.tasks_table.setRowHeight(row_index, 38)
        self._set_summary_value(self.total_tasks_label, len(tasks))
        self._set_summary_value(self.running_tasks_label, status_counts["running"])
        self._set_summary_value(self.pending_tasks_label, status_counts["pending"])
        self._set_summary_value(self.success_tasks_label, status_counts["success"])

    def _status_label(self, status: str) -> str:
        """把内部下载状态转换成更短的中文展示。"""

        labels = {
            "pending": self._text("等待中", "Pending"),
            "running": self._text("下载中", "Running"),
            "paused": self._text("暂停中", "Paused"),
            "success": self._text("完成", "Done"),
            "failed": self._text("失败", "Failed"),
            "canceled": self._text("已取消", "Cancelled"),
        }
        return labels.get(status, status)

    def _apply_format_probe_result(self, result: VideoFormatProbeResult) -> None:
        """把探测到的格式拆成音视频两组，并更新到 UI。"""

        self.formats_title_label.setText(
            self._text(
                f"<b>当前格式结果：</b> {result.title}",
                f"<b>Current formats:</b> {result.title}",
            )
        )

        self._video_formats = tuple(item for item in result.formats if not self._is_audio_only(item))
        self._audio_formats = tuple(item for item in result.formats if self._is_audio_only(item))

        self._populate_video_table()
        self._populate_audio_table()
        self._populate_format_controls(self._video_formats, self._audio_formats)

        if self._video_formats:
            self.video_combo.setCurrentIndex(self._recommend_video_index(self._video_formats) + 1)
        if self._audio_formats:
            self.audio_combo.setCurrentIndex(self._recommend_audio_index(self._audio_formats) + 1)
        self._update_selection_summary()

    def _populate_video_table(self) -> None:
        """把视频格式渲染成更接近人话的展示表格。"""

        table_item = self._table_item_class
        self.video_table.setRowCount(len(self._video_formats))
        for row_index, item in enumerate(self._video_formats):
            self.video_table.setItem(row_index, 0, table_item(item.format_id))
            self.video_table.setItem(row_index, 1, table_item(item.resolution or "-"))
            self.video_table.setItem(row_index, 2, table_item(self._build_video_label(item)))
            self.video_table.setItem(row_index, 3, table_item(item.vcodec or "-"))
            self.video_table.setItem(row_index, 4, table_item(item.filesize_text or "-"))

    def _populate_audio_table(self) -> None:
        """把音频格式单独渲染，避免与视频流混在一起。"""

        table_item = self._table_item_class
        self.audio_table.setRowCount(len(self._audio_formats))
        for row_index, item in enumerate(self._audio_formats):
            self.audio_table.setItem(row_index, 0, table_item(item.format_id))
            self.audio_table.setItem(row_index, 1, table_item(self._build_audio_type(item)))
            self.audio_table.setItem(row_index, 2, table_item(self._build_audio_label(item, row_index)))
            self.audio_table.setItem(row_index, 3, table_item(item.acodec or "-"))
            self.audio_table.setItem(row_index, 4, table_item(item.filesize_text or "-"))

    def _populate_format_controls(
        self,
        video_formats: tuple[VideoFormatOption, ...],
        audio_formats: tuple[VideoFormatOption, ...] = (),
    ) -> None:
        """刷新音视频下拉框，保证选择器与当前探测结果同步。"""

        self.video_combo.blockSignals(True)
        self.audio_combo.blockSignals(True)

        self.video_combo.clear()
        self.video_combo.addItem(self._text("不指定视频流", "Do not pick a video stream"), None)
        for item in video_formats:
            self.video_combo.addItem(self._build_combo_label(item, is_audio=False), item)

        self.audio_combo.clear()
        self.audio_combo.addItem(self._text("不指定音频流", "Do not pick an audio stream"), None)
        for audio_index, item in enumerate(audio_formats):
            self.audio_combo.addItem(self._build_combo_label(item, is_audio=True, audio_index=audio_index), item)

        self.video_combo.blockSignals(False)
        self.audio_combo.blockSignals(False)

    def _flush_ui_events(self) -> None:
        """在主线程中消费后台线程传回的结果消息。"""

        while True:
            try:
                event_type, payload = self._ui_events.get_nowait()
            except Empty:
                break

            if event_type == "formats":
                if self.formats_title_label is None:
                    continue
                self._apply_format_probe_result(payload)
                continue

            if event_type == "message":
                level, message = payload
                self.status_label.setText(message)
                title = self._text("下载结果", "Download Result")
                if "格式" in message or "format" in message.lower():
                    title = self._text("格式探测", "Format Probe")
                self._show_feedback(title, message, level=level)

        # 清理已经结束的线程引用，避免页面长期堆积无用对象。
        self._active_threads = [thread for thread in self._active_threads if thread.is_alive()]

    def _handle_video_table_selection(self) -> None:
        """把视频表格选中行同步到下拉框。"""

        selected_ranges = self.video_table.selectedRanges()
        row_index = selected_ranges[0].topRow() if selected_ranges else -1
        self.video_combo.blockSignals(True)
        self.video_combo.setCurrentIndex(row_index + 1 if row_index >= 0 else 0)
        self.video_combo.blockSignals(False)
        self._update_selection_summary()

    def _handle_audio_table_selection(self) -> None:
        """把音频表格选中行同步到下拉框。"""

        selected_ranges = self.audio_table.selectedRanges()
        row_index = selected_ranges[0].topRow() if selected_ranges else -1
        self.audio_combo.blockSignals(True)
        self.audio_combo.setCurrentIndex(row_index + 1 if row_index >= 0 else 0)
        self.audio_combo.blockSignals(False)
        self._update_selection_summary()

    def _handle_video_combo_selection(self) -> None:
        """把视频下拉框选项同步回表格。"""

        row_index = self.video_combo.currentIndex() - 1
        if row_index >= 0:
            self.video_table.selectRow(row_index)
        else:
            self.video_table.clearSelection()
        self._update_selection_summary()

    def _handle_audio_combo_selection(self) -> None:
        """把音频下拉框选项同步回表格。"""

        row_index = self.audio_combo.currentIndex() - 1
        if row_index >= 0:
            self.audio_table.selectRow(row_index)
        else:
            self.audio_table.clearSelection()
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        """根据当前选择与合并选项，更新下载计划摘要。"""

        manual_selector = self.manual_format_input.text().strip()
        if manual_selector:
            summary = self._text(
                f"下载计划：使用手动格式覆盖 `{manual_selector}` 进行单任务下载。",
                f"Plan: use the manual format override `{manual_selector}` as a single download task.",
            )
            self.selection_summary_label.setText(summary)
            return

        download_plan = self._build_download_plan(
            self.name_input.text().strip() or self._text("未命名任务", "untitled-task")
        )
        self.selection_summary_label.setText(self._describe_download_plan(download_plan))

    def _build_download_plan(self, resolved_name: str) -> tuple[tuple[str, str], ...]:
        """根据当前选择生成真实下载计划。"""

        manual_selector = self.manual_format_input.text().strip()
        if manual_selector:
            return ((resolved_name, manual_selector),)

        selected_video = self.video_combo.currentData()
        selected_audio = self.audio_combo.currentData()
        merge_enabled = self.merge_checkbox.isEnabled() and self.merge_checkbox.isChecked()

        if selected_video and selected_audio and merge_enabled:
            return ((resolved_name, f"{selected_video.format_id}+{selected_audio.format_id}"),)
        if selected_video and selected_audio:
            return (
                (f"{resolved_name}-video", selected_video.format_id),
                (f"{resolved_name}-audio", selected_audio.format_id),
            )
        if selected_video:
            return ((f"{resolved_name}-video", selected_video.format_id),)
        if selected_audio:
            return ((f"{resolved_name}-audio", selected_audio.format_id),)
        return ((resolved_name, self.context.download_service.DEFAULT_FORMAT_SELECTOR),)

    def _describe_download_plan(self, download_plan: tuple[tuple[str, str], ...]) -> str:
        """把下载计划翻译成界面上更容易看懂的说明。"""

        if len(download_plan) == 1 and download_plan[0][1] == self.context.download_service.DEFAULT_FORMAT_SELECTOR:
            return self._text(
                "下载计划：当前没有指定具体格式，将使用自动选择。",
                "Plan: no explicit format is selected, so the automatic selector will be used.",
            )

        lines = [self._text("下载计划：", "Plan:")]
        for display_name, format_selector in download_plan:
            lines.append(f"- {display_name}: {format_selector}")
        return "\n".join(lines)

    def _configure_table(self, table, *, header_stretch_column: int) -> None:
        """统一设置表格的交互方式和列宽策略。"""

        from PySide6.QtWidgets import QAbstractItemView, QHeaderView

        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        header = table.horizontalHeader()
        for index in range(table.columnCount()):
            mode = QHeaderView.ResizeToContents
            if index == header_stretch_column:
                mode = QHeaderView.Stretch
            header.setSectionResizeMode(index, mode)

    def _configure_task_queue_table(self) -> None:
        """下载任务表使用固定进度列，避免进度条和保存路径互相挤压。"""

        from PySide6.QtWidgets import QHeaderView

        header = self.tasks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.tasks_table.setColumnWidth(2, 76)
        self.tasks_table.setColumnWidth(3, 190)

    def _build_combo_label(self, item: VideoFormatOption, *, is_audio: bool, audio_index: int | None = None) -> str:
        """把格式对象变成下拉框里更易读的一行文本。"""

        if is_audio:
            return f"{item.format_id} | {self._build_audio_type(item)} | {self._build_audio_label(item, audio_index or 0)}"
        return f"{item.format_id} | {item.resolution or '-'} | {self._build_video_label(item)}"

    def _build_video_label(self, item: VideoFormatOption) -> str:
        """根据编码和附加信息，把视频流翻译成更贴近用户语言的标签。"""

        codec = (item.vcodec or "").lower()
        if "avc" in codec:
            trait = self._text("兼容优先", "Compatibility first")
        elif "hev1" in codec or "hevc" in codec or "hvc1" in codec:
            trait = self._text("体积更小", "Smaller size")
        elif "av01" in codec or "av1" in codec:
            trait = self._text("新编码 AV1", "New AV1 codec")
        else:
            trait = self._text("标准视频流", "Standard video stream")

        if item.note:
            return f"{trait} | {item.note}"
        return trait

    def _build_audio_type(self, item: VideoFormatOption) -> str:
        """给音频流一个更好理解的类型说明。"""

        return self._text("纯音频", "Audio only")

    def _build_audio_label(self, item: VideoFormatOption, audio_index: int) -> str:
        """给音频流加上简单推荐语，避免用户面对纯编号无从下手。"""

        if audio_index == self._recommend_audio_index(self._audio_formats):
            priority = self._text("推荐音频", "Recommended audio")
        else:
            priority = self._text("备选音频", "Alternative audio")

        if item.note:
            return f"{priority} | {item.note}"
        return priority

    def _is_audio_only(self, item: VideoFormatOption) -> bool:
        """判断一个格式是否是纯音频流。"""

        resolution = (item.resolution or "").lower()
        vcodec = (item.vcodec or "").lower()
        return resolution == "audio only" or vcodec == "none"

    def _recommend_video_index(self, items: tuple[VideoFormatOption, ...]) -> int:
        """优先推荐最高分辨率里兼容性更好的 AVC 视频流。"""

        best_index = 0
        best_score = (-1, -1, -1.0)
        for index, item in enumerate(items):
            width, height = self._parse_resolution(item.resolution)
            area = width * height
            codec_score = self._video_codec_rank(item.vcodec)
            size_score = self._parse_size_text(item.filesize_text)
            score = (area, codec_score, size_score)
            if score > best_score:
                best_index = index
                best_score = score
        return best_index

    def _recommend_audio_index(self, items: tuple[VideoFormatOption, ...]) -> int:
        """优先推荐体积更大的音频流，作为较高音质的近似判断。"""

        best_index = 0
        best_score = -1.0
        for index, item in enumerate(items):
            size_score = self._parse_size_text(item.filesize_text)
            if size_score > best_score:
                best_index = index
                best_score = size_score
        return best_index

    def _video_codec_rank(self, codec: str | None) -> int:
        """给常见视频编码一个简单的偏好顺序。"""

        value = (codec or "").lower()
        if "avc" in value:
            return 3
        if "hev1" in value or "hevc" in value or "hvc1" in value:
            return 2
        if "av01" in value or "av1" in value:
            return 1
        return 0

    def _parse_resolution(self, resolution: str | None) -> tuple[int, int]:
        """把 `1920x1080` 解析成宽高，便于做推荐排序。"""

        raw = (resolution or "").lower()
        if "x" not in raw:
            return (0, 0)
        width_text, height_text = raw.split("x", maxsplit=1)
        try:
            return (int(width_text), int(height_text))
        except ValueError:
            return (0, 0)

    def _parse_size_text(self, size_text: str | None) -> float:
        """把 `12.4MiB` 之类的文本大小转成可比较的数值。"""

        if not size_text:
            return 0.0

        normalized = size_text.strip().lower()
        unit_map = {
            "kib": 1024.0,
            "mib": 1024.0 * 1024.0,
            "gib": 1024.0 * 1024.0 * 1024.0,
            "kb": 1000.0,
            "mb": 1000.0 * 1000.0,
            "gb": 1000.0 * 1000.0 * 1000.0,
            "b": 1.0,
        }
        for unit, multiplier in unit_map.items():
            if normalized.endswith(unit):
                number_text = normalized[: -len(unit)].strip()
                try:
                    return float(number_text) * multiplier
                except ValueError:
                    return 0.0
        try:
            return float(normalized)
        except ValueError:
            return 0.0

    def _text(self, zh: str, en: str):
        """根据当前语言返回对应文本。"""

        return zh if self.context.settings.ui_language == "zh-CN" else en

    def _show_feedback(self, title: str, message: str, level: str = "info") -> None:
        """用统一弹窗反馈探测和下载结果。"""

        if level == "error":
            self._message_box_class.critical(None, title, message)
        elif level == "warning":
            self._message_box_class.warning(None, title, message)
        else:
            self._message_box_class.information(None, title, message)
