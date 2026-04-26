from __future__ import annotations

from collections.abc import Callable

from bilibili_tool.application import AppContext
from bilibili_tool.domain import SourceKind, SourceRecord, UserProbeCandidate
from bilibili_tool.infra.browser import BrowserUserSearch


class SourcesPage:
    """来源管理台，负责来源解析、保存、同步和已保存来源维护。"""

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.status_label = None
        self.preview_label = None
        self.next_step_label = None
        self.live_probe_label = None
        self.kind_combo = None
        self.user_kind_button = None
        self.favorite_kind_button = None
        self.video_kind_button = None
        self.value_input = None
        self.name_input = None
        self.source_list = None
        self.detail_name_label = None
        self.detail_meta_label = None
        self.detail_url_label = None
        self.detail_sync_label = None
        self.detail_count_label = None
        self.detail_pub_label = None
        self.detail_status_label = None
        self.detail_sync_once_button = None
        self.detail_sync_all_button = None
        self.detail_queue_button = None
        self.detail_rename_button = None
        self.detail_delete_button = None
        self.sync_progress = None
        self.sync_busy_label = None
        self._message_box_class = None
        self._input_dialog_class = None
        self._after_sync_callback: Callable[[], None] | None = None
        self._browser_user_search: BrowserUserSearch | None = None
        self._sources: list[SourceRecord] = []
        self._source_stats: dict[int, tuple[int, int]] = {}
        self._selected_source_id: int | None = None
        self._selected_source_row: int | None = None
        self._stats_refresh_token = 0
        self._page_stylesheet = ""
        self._is_syncing = False

    def set_after_sync_callback(self, callback: Callable[[], None]) -> None:
        """注册同步成功后的刷新回调，让资源库页面及时更新。"""

        self._after_sync_callback = callback

    def build(self):
        """构造来源管理台：左侧来源列表、右侧详情、底部解析区。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QAbstractItemView,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QSizePolicy,
            QSplitter,
            QButtonGroup,
            QVBoxLayout,
            QWidget,
        )

        self._message_box_class = QMessageBox
        self._input_dialog_class = QInputDialog

        widget = QWidget()
        widget.setObjectName("sourcesPage")
        root_layout = QVBoxLayout(widget)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(14)

        header_layout = QHBoxLayout()
        title_block = QVBoxLayout()
        title_label = QLabel(self._text("来源管理", "Source Management"))
        title_label.setObjectName("pageTitle")
        intro_label = QLabel(
            self._text(
                "集中管理 UP 主、收藏夹和单视频来源；选中来源后可同步、入队、重命名或删除。",
                "Manage user, favorite, and single-video sources. Select a source to sync, queue, rename, or delete it.",
            )
        )
        intro_label.setObjectName("pageSubtitle")
        intro_label.setWordWrap(True)
        title_block.addWidget(title_label)
        title_block.addWidget(intro_label)
        header_layout.addLayout(title_block, 1)
        root_layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("sourceSplitter")
        root_layout.addWidget(splitter, 1)

        left_card = QFrame()
        left_card.setObjectName("sourceCard")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 14, 16, 16)
        left_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_title = QLabel(self._text("来源列表", "Sources"))
        list_title.setObjectName("sectionTitle")
        new_button = QPushButton(self._text("+ 新建来源", "+ New Source"))
        new_button.setObjectName("softButton")
        new_button.clicked.connect(self._open_source_dialog)
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(new_button)
        left_layout.addLayout(list_header)

        self.source_list = _RelayoutListWidget(self._schedule_source_list_relayout)
        self.source_list.setObjectName("sourceList")
        self.source_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.source_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_list.setSpacing(4)
        self.source_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.source_list.customContextMenuRequested.connect(self._show_source_context_menu)
        self.source_list.currentRowChanged.connect(self._handle_source_selection_changed)
        left_layout.addWidget(self.source_list, 1)

        right_card = QFrame()
        right_card.setObjectName("sourceCard")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        detail_title = QLabel(self._text("来源详情", "Source Details"))
        detail_title.setObjectName("sectionTitle")
        right_layout.addWidget(detail_title)

        self.detail_name_label = QLabel(self._text("请选择一个来源", "Select a source"))
        self.detail_name_label.setObjectName("detailName")
        self.detail_meta_label = QLabel(self._text("左侧列表用于管理已保存来源。", "Use the list on the left to manage saved sources."))
        self.detail_meta_label.setObjectName("mutedText")
        self.detail_meta_label.setWordWrap(True)
        self.detail_url_label = QLabel("-")
        self.detail_url_label.setObjectName("urlText")
        self.detail_url_label.setWordWrap(True)
        right_layout.addWidget(self.detail_name_label)
        right_layout.addWidget(self.detail_meta_label)
        right_layout.addWidget(self.detail_url_label)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        self.detail_sync_label = self._build_metric("最近同步", "Last Sync")
        self.detail_count_label = self._build_metric("视频数量", "Videos")
        self.detail_pub_label = self._build_metric("发布时间覆盖", "Publish Time")
        self.detail_status_label = self._build_metric("状态", "Status")
        metrics.addWidget(self.detail_sync_label, 0, 0)
        metrics.addWidget(self.detail_count_label, 0, 1)
        metrics.addWidget(self.detail_pub_label, 1, 0)
        metrics.addWidget(self.detail_status_label, 1, 1)
        right_layout.addLayout(metrics)

        action_box = QFrame()
        action_box.setObjectName("actionBox")
        action_layout = QGridLayout(action_box)
        action_layout.setContentsMargins(12, 12, 12, 12)
        action_layout.setHorizontalSpacing(10)
        action_layout.setVerticalSpacing(10)
        self.detail_sync_once_button = QPushButton(self._text("同步第一页", "Sync First Page"))
        self.detail_sync_once_button.setObjectName("primaryButton")
        self.detail_sync_once_button.clicked.connect(self._sync_selected_source_once)
        self.detail_sync_all_button = QPushButton(self._text("全量同步", "Full Sync"))
        self.detail_sync_all_button.clicked.connect(self._sync_selected_source_all)
        self.detail_queue_button = QPushButton(self._text("加入下载队列", "Queue Downloads"))
        self.detail_queue_button.clicked.connect(self._queue_selected_source_videos)
        self.detail_rename_button = QPushButton(self._text("重命名", "Rename"))
        self.detail_rename_button.clicked.connect(self._rename_selected_source)
        self.detail_delete_button = QPushButton(self._text("删除", "Delete"))
        self.detail_delete_button.setObjectName("dangerButton")
        self.detail_delete_button.clicked.connect(self._delete_selected_source)
        action_layout.addWidget(self.detail_sync_once_button, 0, 0)
        action_layout.addWidget(self.detail_sync_all_button, 0, 1)
        action_layout.addWidget(self.detail_queue_button, 1, 0, 1, 2)
        action_layout.addWidget(self.detail_rename_button, 2, 0)
        action_layout.addWidget(self.detail_delete_button, 2, 1)
        self.sync_busy_label = QLabel(self._text("准备同步。", "Ready to sync."))
        self.sync_busy_label.setObjectName("syncBusyLabel")
        self.sync_busy_label.setVisible(False)
        self.sync_progress = QProgressBar()
        self.sync_progress.setObjectName("syncProgress")
        self.sync_progress.setRange(0, 0)
        self.sync_progress.setTextVisible(False)
        self.sync_progress.setVisible(False)
        action_layout.addWidget(self.sync_busy_label, 3, 0, 1, 2)
        action_layout.addWidget(self.sync_progress, 4, 0, 1, 2)
        right_layout.addWidget(action_box)
        right_layout.addStretch(1)

        splitter.addWidget(left_card)
        splitter.addWidget(right_card)
        splitter.setSizes([430, 620])
        self._apply_styles(widget)
        self._refresh_sources()
        self._schedule_source_list_relayout()
        return widget

    def _text(self, zh: str, en: str) -> str:
        """根据当前 UI 语言返回文本。"""

        return zh if self.context.settings.ui_language == "zh-CN" else en

    def _build_metric(self, zh_title: str, en_title: str):
        """创建详情区的指标卡片。"""

        from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel(self._text(zh_title, en_title))
        title.setObjectName("metricTitle")
        value = QLabel("-")
        value.setObjectName("metricValue")
        value.setProperty("metricValue", True)
        layout.addWidget(title)
        layout.addWidget(value)
        return card

    def _metric_value_label(self, card):
        """取出指标卡片里的值标签，避免为每个字段额外保存变量。"""

        labels = card.findChildren(type(self.detail_name_label)) if self.detail_name_label is not None else []
        for label in labels:
            if label.property("metricValue"):
                return label
        return None

    def _set_metric(self, card, value: str) -> None:
        """更新指标卡片值。"""

        label = self._metric_value_label(card)
        if label is not None and label.text() != value:
            label.setText(value)

    def _apply_styles(self, widget) -> None:
        """集中定义来源页视觉风格，避免样式散落在各个控件里。"""

        stylesheet = """
            #sourcesPage {
                background: #f6f3ec;
                color: #1f2933;
            }
            #pageTitle {
                font-size: 22px;
                font-weight: 700;
                color: #182635;
            }
            #pageSubtitle, #mutedText, .QLabel#mutedText {
                color: #667085;
                font-size: 12px;
            }
            #sourceCard, #draftGroup {
                background: #fffdf8;
                border: 1px solid #ded8cb;
                border-radius: 14px;
            }
            #sourceDialog {
                background: #f6f3ec;
            }
            #draftGroup {
                margin-top: 8px;
                font-weight: 600;
            }
            #fieldLabel {
                color: #415466;
                font-size: 12px;
                font-weight: 700;
            }
            #kindSelector {
                background: #eef4f6;
                border: 1px solid #d5e2e7;
                border-radius: 12px;
            }
            #kindPill {
                min-height: 28px;
                padding: 5px 13px;
                border: 1px solid transparent;
                border-radius: 9px;
                background: transparent;
                color: #526473;
                font-weight: 700;
            }
            #kindPill:hover {
                background: #f8fcfd;
                border-color: #c5dce5;
            }
            #kindPill:checked {
                background: #ffffff;
                color: #12658a;
                border-color: #9ccfe0;
            }
            #sectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #1e3448;
            }
            #sourceList {
                background: transparent;
                border: none;
                outline: 0;
            }
            #sourceList::item {
                margin: 0;
            }
            #sourceList::item:selected {
                background: transparent;
            }
            #sourceItemShell {
                background: transparent;
                border: none;
            }
            #sourceItem {
                background: #ffffff;
                border: 1px solid #e8e2d7;
                border-radius: 12px;
                min-height: 104px;
                max-height: 104px;
            }
            #sourceItem[selected="true"] {
                background: #eaf5ff;
                border-color: #8ec5e8;
            }
            #sourceItemTitle {
                font-size: 14px;
                font-weight: 700;
                color: #182635;
                min-height: 22px;
            }
            #sourceItemMeta {
                color: #667085;
                font-size: 12px;
                min-height: 18px;
            }
            #sourceBadge {
                background: #edf7f9;
                color: #15708a;
                border: 1px solid #bee1ea;
                border-radius: 8px;
                padding: 2px 7px;
                font-size: 11px;
                min-width: 54px;
                min-height: 22px;
            }
            #detailName {
                font-size: 24px;
                font-weight: 800;
                color: #172536;
            }
            #urlText {
                color: #35627d;
                background: #f4f8fa;
                border: 1px solid #e1edf2;
                border-radius: 8px;
                padding: 8px;
            }
            #metricCard, #actionBox, #statusPanel {
                background: #ffffff;
                border: 1px solid #e8e2d7;
                border-radius: 12px;
            }
            #dialogBody {
                background: #fffdf8;
                border: 1px solid #ded8cb;
                border-radius: 14px;
            }
            #metricTitle {
                color: #7a8694;
                font-size: 12px;
            }
            #metricValue {
                color: #172536;
                font-size: 16px;
                font-weight: 700;
            }
            #syncBusyLabel {
                color: #176d8f;
                font-weight: 700;
                padding-top: 4px;
            }
            #syncProgress {
                min-height: 8px;
                max-height: 8px;
                border: 1px solid #b9ddea;
                border-radius: 4px;
                background: #eef7fb;
            }
            #syncProgress::chunk {
                border-radius: 4px;
                background: #2288b8;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cfd8df;
                border-radius: 9px;
                padding: 7px 12px;
                color: #1f3447;
            }
            QPushButton:hover {
                background: #f2f8fb;
                border-color: #8ec5e8;
            }
            QPushButton:disabled {
                color: #a4aab2;
                background: #f3f4f6;
                border-color: #e2e5e9;
            }
            #primaryButton {
                background: #2288b8;
                border-color: #1f7fae;
                color: white;
                font-weight: 700;
            }
            #primaryButton:hover {
                background: #1b78a5;
            }
            #softButton {
                background: #eef7fb;
                border-color: #b9ddea;
                color: #176d8f;
                font-weight: 700;
            }
            #dangerButton {
                color: #b42318;
                border-color: #f0b8b2;
                background: #fff7f6;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #cfd8df;
                border-radius: 8px;
                padding: 6px 9px;
            }
            #draftInput {
                min-height: 30px;
                border-radius: 10px;
                background: #fffefa;
                border-color: #d6e0e5;
                padding-left: 12px;
                padding-right: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #2288b8;
            }
            #statusText {
                color: #344054;
            }
            """
        self._page_stylesheet = stylesheet
        widget.setStyleSheet(stylesheet)

    def _show_feedback(self, title: str, message: str, level: str = "info") -> None:
        """弹出更明确的结果提示，避免按钮动作看起来像没反应。"""

        box = self._message_box_class
        if level == "error":
            box.critical(None, title, message)
        elif level == "warning":
            box.warning(None, title, message)
        else:
            box.information(None, title, message)

    def _set_status_text(self, message: str) -> None:
        """如果新建弹窗打开着，就更新弹窗状态；否则只静默记录动作结果。"""

        if self.status_label is not None:
            self.status_label.setText(message)

    def _set_probe_text(self, message: str) -> None:
        """如果新建弹窗打开着，就更新弹窗里的探测/同步结果。"""

        if self.live_probe_label is not None:
            self.live_probe_label.setText(message)

    def _set_sync_busy(self, busy: bool, message: str | None = None) -> None:
        """切换同步忙碌态，防止重复点击并给用户明确反馈。"""

        self._is_syncing = busy
        if self.sync_busy_label is not None:
            self.sync_busy_label.setText(message or self._text("正在同步，请稍候...", "Syncing, please wait..."))
            self.sync_busy_label.setVisible(busy)
        if self.sync_progress is not None:
            self.sync_progress.setVisible(busy)
        self.source_list.setEnabled(not busy)
        self._update_detail_panel()

    def _run_sync_with_busy_state(self, source: SourceRecord, message: str, action) -> None:
        """先刷新忙碌态，再在事件循环下一拍执行同步动作。"""

        if self._is_syncing:
            return
        self._selected_source_id = source.id
        self._set_sync_busy(True, message)

        from PySide6.QtCore import QTimer

        # 留出一小段时间给 Qt 完成重绘，让忙碌条先显示出来再进入同步流程。
        QTimer.singleShot(80, lambda: self._finish_sync_action(action))

    def _finish_sync_action(self, action) -> None:
        """执行同步动作并确保无论成功失败都会恢复按钮。"""

        try:
            action()
        finally:
            self._set_sync_busy(False)

    def _open_source_dialog(self) -> None:
        """打开新建来源弹窗，并在保存后刷新管理台。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout

        dialog = QDialog(self.source_list)
        dialog.setObjectName("sourceDialog")
        dialog.setWindowTitle(self._text("新建 / 解析来源", "Create / Resolve Source"))
        dialog.setMinimumSize(980, 360)
        dialog.setModal(True)
        dialog.setStyleSheet(self._page_stylesheet)

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(12)

        body = QFrame()
        body.setObjectName("dialogBody")
        layout = QGridLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        title_label = QLabel(self._text("新建 / 解析来源", "Create / Resolve Source"))
        title_label.setObjectName("sectionTitle")
        hint_label = QLabel(
            self._text(
                "先选择来源类型并输入链接或 ID，解析确认后保存到左侧来源列表。",
                "Choose a source type, enter a link or id, resolve it, then save it into the source list.",
            )
        )
        hint_label.setObjectName("mutedText")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label, 0, 0, 1, 6)
        layout.addWidget(hint_label, 1, 0, 1, 6)

        kind_combo, kind_selector, user_button, favorite_button, video_button = self._build_kind_selector()
        value_input, name_input = self._build_dialog_inputs()
        preview_button = QPushButton(self._text("解析来源", "Resolve Source"))
        preview_button.setObjectName("primaryButton")
        probe_button = QPushButton(self._text("单次探测", "Probe Once"))
        save_button = QPushButton(self._text("保存来源", "Save Source"))

        type_label = QLabel(self._text("来源类型", "Source Type"))
        type_label.setObjectName("fieldLabel")
        value_label = QLabel(self._text("来源输入", "Source Input"))
        value_label.setObjectName("fieldLabel")
        name_label = QLabel(self._text("显示名称", "Display Name"))
        name_label.setObjectName("fieldLabel")
        layout.addWidget(type_label, 2, 0)
        layout.addWidget(kind_selector, 2, 1)
        layout.addWidget(value_label, 2, 2)
        layout.addWidget(value_input, 2, 3, 1, 3)
        layout.addWidget(name_label, 3, 0)
        layout.addWidget(name_input, 3, 1, 1, 2)
        layout.addWidget(preview_button, 3, 3)
        layout.addWidget(probe_button, 3, 4)
        layout.addWidget(save_button, 3, 5)
        layout.setColumnMinimumWidth(0, 72)
        layout.setColumnMinimumWidth(1, 260)
        layout.setColumnStretch(3, 1)

        status_panel = QFrame()
        status_panel.setObjectName("statusPanel")
        status_layout = QGridLayout(status_panel)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setHorizontalSpacing(12)
        status_layout.setVerticalSpacing(6)
        status_label = QLabel(self._text("准备就绪。", "Ready."))
        preview_label = QLabel(self._text("解析预览：尚未生成。", "Preview: not generated yet."))
        next_step_label = QLabel(self._text("下一步说明：尚未生成。", "Next step: not generated yet."))
        live_probe_label = QLabel(self._text("实时探测：尚未执行。", "Live probe: not executed yet."))
        for label in (status_label, preview_label, next_step_label, live_probe_label):
            label.setObjectName("statusText")
            label.setWordWrap(True)
        status_layout.addWidget(QLabel(self._text("状态", "Status")), 0, 0)
        status_layout.addWidget(status_label, 0, 1)
        status_layout.addWidget(QLabel(self._text("预览", "Preview")), 1, 0)
        status_layout.addWidget(preview_label, 1, 1)
        status_layout.addWidget(QLabel(self._text("下一步", "Next")), 2, 0)
        status_layout.addWidget(next_step_label, 2, 1)
        status_layout.addWidget(QLabel(self._text("探测", "Probe")), 3, 0)
        status_layout.addWidget(live_probe_label, 3, 1)
        layout.addWidget(status_panel, 4, 0, 1, 6)

        close_row = QGridLayout()
        close_button = QPushButton(self._text("关闭", "Close"))
        close_button.clicked.connect(dialog.reject)
        close_row.addWidget(close_button, 0, 5, Qt.AlignRight)
        outer_layout.addWidget(body)
        outer_layout.addLayout(close_row)

        previous_controls = self._capture_draft_controls()
        self._bind_draft_controls(
            kind_combo=kind_combo,
            user_kind_button=user_button,
            favorite_kind_button=favorite_button,
            video_kind_button=video_button,
            value_input=value_input,
            name_input=name_input,
            status_label=status_label,
            preview_label=preview_label,
            next_step_label=next_step_label,
            live_probe_label=live_probe_label,
        )

        preview_button.clicked.connect(self._preview_source)
        probe_button.clicked.connect(self._probe_once)
        save_button.clicked.connect(lambda: self._save_source(close_dialog=dialog))

        value_input.setFocus()
        dialog.finished.connect(lambda _result: self._bind_draft_controls(**previous_controls))
        dialog.exec()

    def _build_kind_selector(self):
        """创建弹窗里的来源类型胶囊选择器。"""

        from PySide6.QtWidgets import QButtonGroup, QComboBox, QFrame, QHBoxLayout, QPushButton

        kind_combo = QComboBox()
        kind_combo.addItems([kind.value for kind in SourceKind])
        kind_combo.setVisible(False)

        kind_selector = QFrame()
        kind_selector.setObjectName("kindSelector")
        kind_layout = QHBoxLayout(kind_selector)
        kind_layout.setContentsMargins(4, 4, 4, 4)
        kind_layout.setSpacing(4)
        kind_group = QButtonGroup(kind_selector)
        kind_group.setExclusive(True)
        user_button = QPushButton(self._text("UP 主", "User"))
        favorite_button = QPushButton(self._text("收藏夹", "Favorite"))
        video_button = QPushButton(self._text("单视频", "Video"))
        for button, kind in (
            (user_button, SourceKind.USER),
            (favorite_button, SourceKind.FAVORITE),
            (video_button, SourceKind.VIDEO),
        ):
            button.setObjectName("kindPill")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, selected_kind=kind: self._set_kind(selected_kind))
            kind_group.addButton(button)
            kind_layout.addWidget(button)
        user_button.setChecked(True)
        kind_combo.currentTextChanged.connect(self._sync_kind_buttons_from_combo)
        return kind_combo, kind_selector, user_button, favorite_button, video_button

    def _build_dialog_inputs(self):
        """创建弹窗输入框。"""

        from PySide6.QtWidgets import QLineEdit

        value_input = QLineEdit()
        value_input.setObjectName("draftInput")
        value_input.setPlaceholderText(
            self._text(
                "输入 UID、用户名、主页链接、收藏夹链接或 BV 号",
                "Enter a UID, username, homepage URL, favorite URL, or BV id",
            )
        )
        name_input = QLineEdit()
        name_input.setObjectName("draftInput")
        name_input.setPlaceholderText(self._text("可选显示名称", "Optional display name"))
        return value_input, name_input

    def _capture_draft_controls(self) -> dict:
        """保存当前弹窗控件引用，弹窗关闭后恢复为空状态。"""

        return {
            "kind_combo": self.kind_combo,
            "user_kind_button": self.user_kind_button,
            "favorite_kind_button": self.favorite_kind_button,
            "video_kind_button": self.video_kind_button,
            "value_input": self.value_input,
            "name_input": self.name_input,
            "status_label": self.status_label,
            "preview_label": self.preview_label,
            "next_step_label": self.next_step_label,
            "live_probe_label": self.live_probe_label,
        }

    def _bind_draft_controls(
        self,
        *,
        kind_combo,
        user_kind_button,
        favorite_kind_button,
        video_kind_button,
        value_input,
        name_input,
        status_label,
        preview_label,
        next_step_label,
        live_probe_label,
    ) -> None:
        """把解析/探测/保存逻辑绑定到当前弹窗控件。"""

        self.kind_combo = kind_combo
        self.user_kind_button = user_kind_button
        self.favorite_kind_button = favorite_kind_button
        self.video_kind_button = video_kind_button
        self.value_input = value_input
        self.name_input = name_input
        self.status_label = status_label
        self.preview_label = preview_label
        self.next_step_label = next_step_label
        self.live_probe_label = live_probe_label

    def _set_kind(self, kind: SourceKind) -> None:
        """通过胶囊按钮切换来源类型，并同步隐藏的业务下拉框。"""

        if self.kind_combo.currentText() != kind.value:
            self.kind_combo.setCurrentText(kind.value)
        self._sync_kind_buttons_from_combo(kind.value)

    def _sync_kind_buttons_from_combo(self, value: str) -> None:
        """保持胶囊按钮和隐藏下拉框状态一致。"""

        mapping = {
            SourceKind.USER.value: self.user_kind_button,
            SourceKind.FAVORITE.value: self.favorite_kind_button,
            SourceKind.VIDEO.value: self.video_kind_button,
        }
        for kind_value, button in mapping.items():
            if button is not None:
                button.setChecked(kind_value == value)

    def _refresh_sources(self, select_source_id: int | None = None) -> None:
        """重新加载来源列表、统计信息和详情面板。"""

        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QListWidgetItem

        previous_id = select_source_id if select_source_id is not None else self._selected_source_id
        self._sources = self.context.source_service.list_sources()
        self._source_stats = {}

        self.source_list.blockSignals(True)
        self.source_list.clear()
        selected_row = -1
        for row_index, source in enumerate(self._sources):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 118))
            item.setData(256, source.id)
            self.source_list.addItem(item)
            is_selected = previous_id == source.id
            if is_selected:
                selected_row = row_index
            self.source_list.setItemWidget(item, self._build_source_item(source, selected=is_selected))
        self.source_list.blockSignals(False)

        if selected_row < 0 and self._sources:
            selected_row = 0
        if selected_row >= 0:
            self.source_list.setCurrentRow(selected_row)
            self._selected_source_id = self._sources[selected_row].id
            self._selected_source_row = selected_row
        else:
            self._selected_source_id = None
            self._selected_source_row = None
        self._refresh_source_item_selection()
        self._update_detail_panel()
        self._schedule_source_list_relayout()
        self._schedule_source_stats_refresh()

    def _schedule_source_stats_refresh(self) -> None:
        """来源列表先显示，再延迟统计视频数量，降低切到来源页时的同步卡顿。"""

        from PySide6.QtCore import QTimer

        self._stats_refresh_token += 1
        token = self._stats_refresh_token
        QTimer.singleShot(80, lambda: self._refresh_source_stats(token))

    def _refresh_source_stats(self, token: int) -> None:
        """延迟计算来源统计并回填卡片，避免进入页面时阻塞首屏显示。"""

        if token != self._stats_refresh_token or self.source_list is None:
            return
        stats: dict[int, tuple[int, int]] = {}
        for source in self._sources:
            if source.id is not None:
                stats[source.id] = self.context.source_service.get_source_video_stats(source.id)
        if token != self._stats_refresh_token:
            return
        self._source_stats = stats
        self._rebuild_source_item_widgets()
        self._update_detail_panel()
        self._schedule_source_list_relayout()

    def _rebuild_source_item_widgets(self) -> None:
        """只重建左侧来源卡片，不重新读取来源列表。"""

        if self.source_list is None:
            return
        self.source_list.blockSignals(True)
        for row_index, source in enumerate(self._sources):
            item = self.source_list.item(row_index)
            if item is None:
                continue
            self.source_list.setItemWidget(item, self._build_source_item(source, selected=source.id == self._selected_source_id))
        self.source_list.blockSignals(False)
        self._refresh_source_item_selection()

    def _schedule_source_list_relayout(self) -> None:
        """延迟同步来源列表 item 高度，避免首次进入页面时 Qt 还没完成布局。"""

        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._sync_source_list_item_layout)
        QTimer.singleShot(80, self._sync_source_list_item_layout)
        QTimer.singleShot(200, self._sync_source_list_item_layout)

    def _sync_source_list_item_layout(self) -> None:
        """只重设来源条目高度，不强行抢占 Qt 的宽度布局。"""

        from PySide6.QtCore import QSize

        if self.source_list is None:
            return
        for row_index in range(self.source_list.count()):
            item = self.source_list.item(row_index)
            item.setSizeHint(QSize(0, 118))
            widget = self.source_list.itemWidget(item)
            if widget is not None:
                widget.setMinimumHeight(116)
                widget.setMaximumHeight(116)
        self.source_list.doItemsLayout()
        self.source_list.viewport().update()

    def _build_source_item(self, source: SourceRecord, *, selected: bool):
        """创建左侧来源列表的卡片行。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy

        total, pub_count = self._source_stats.get(source.id or -1, (0, 0))
        shell = QFrame()
        shell.setObjectName("sourceItemShell")
        shell.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 5, 14, 5)
        shell_layout.setSpacing(0)
        shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        shell.setMinimumHeight(116)
        shell.setMaximumHeight(116)

        card = QFrame()
        card.setObjectName("sourceItem")
        card.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        card.setProperty("selected", "true" if selected else "false")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(104)
        card.setMaximumHeight(104)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        title = QLabel(source.display_name)
        title.setObjectName("sourceItemTitle")
        title.setMinimumHeight(22)
        title.setWordWrap(False)
        title.setToolTip(source.display_name)
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        badge = QLabel(self._kind_label(source.kind))
        badge.setObjectName("sourceBadge")
        badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        badge.setMinimumSize(54, 22)
        badge.setAlignment(Qt.AlignCenter)
        top_row.addWidget(title, 1)
        top_row.addWidget(badge)
        layout.addLayout(top_row)

        meta = QLabel(
            self._text(
                f"{total} 个视频 · 发布时间 {pub_count}/{total}",
                f"{total} videos · publish time {pub_count}/{total}",
            )
        )
        meta.setObjectName("sourceItemMeta")
        meta.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        meta.setMinimumHeight(18)
        meta.setWordWrap(False)
        layout.addWidget(meta)

        sync_text = self._format_datetime(source.last_sync_at) if source.last_sync_at else self._text("尚未同步", "Never synced")
        status = QLabel(self._text(f"● 正常 · {sync_text}", f"● OK · {sync_text}"))
        status.setObjectName("sourceItemMeta")
        status.setMinimumHeight(18)
        status.setWordWrap(False)
        layout.addWidget(status)
        shell_layout.addWidget(card)
        shell._source_card = card
        return shell

    def _refresh_source_item_selection(self) -> None:
        """刷新左侧卡片的选中态样式。"""

        for row_index, source in enumerate(self._sources):
            self._set_source_item_selected(row_index, source.id == self._selected_source_id)

    def _set_source_item_selected(self, row_index: int | None, selected: bool) -> None:
        """只刷新单个来源卡片的选中态，避免切换来源时整列重绘导致卡顿。"""

        if row_index is None or self.source_list is None:
            return
        if row_index < 0 or row_index >= self.source_list.count():
            return
        item = self.source_list.item(row_index)
        widget = self.source_list.itemWidget(item)
        if widget is None:
            return
        card = getattr(widget, "_source_card", widget)
        next_state = "true" if selected else "false"
        if card.property("selected") == next_state:
            return
        card.setProperty("selected", next_state)
        card.style().unpolish(card)
        card.style().polish(card)
        card.update()

    def _handle_source_selection_changed(self, row_index: int) -> None:
        """左侧来源切换时刷新右侧详情。"""

        previous_row = self._selected_source_row
        if row_index < 0 or row_index >= len(self._sources):
            self._selected_source_id = None
            self._selected_source_row = None
        else:
            self._selected_source_id = self._sources[row_index].id
            self._selected_source_row = row_index
        if previous_row != self._selected_source_row:
            self._set_source_item_selected(previous_row, False)
            self._set_source_item_selected(self._selected_source_row, True)
        self._update_detail_panel()

    def _selected_source(self) -> SourceRecord | None:
        """返回当前选中的来源记录。"""

        if self._selected_source_id is None:
            return None
        # 优先使用当前行缓存，避免高频切换来源时每次都遍历来源列表。
        if self._selected_source_row is not None and 0 <= self._selected_source_row < len(self._sources):
            source = self._sources[self._selected_source_row]
            if source.id == self._selected_source_id:
                return source
        return next((source for source in self._sources if source.id == self._selected_source_id), None)

    def _update_detail_panel(self) -> None:
        """把当前来源详情同步到右侧面板。"""

        source = self._selected_source()
        has_source = source is not None
        for button in (
            self.detail_sync_once_button,
            self.detail_sync_all_button,
            self.detail_queue_button,
            self.detail_rename_button,
            self.detail_delete_button,
        ):
            button.setEnabled(has_source and not self._is_syncing)

        if source is None:
            self.detail_name_label.setText(self._text("请选择一个来源", "Select a source"))
            self.detail_meta_label.setText(self._text("左侧列表用于管理已保存来源。", "Use the list on the left to manage saved sources."))
            self.detail_url_label.setText("-")
            for card in (self.detail_sync_label, self.detail_count_label, self.detail_pub_label, self.detail_status_label):
                self._set_metric(card, "-")
            return

        total, pub_count = self._source_stats.get(source.id or -1, (0, 0))
        self.detail_name_label.setText(source.display_name)
        self.detail_meta_label.setText(f"{self._kind_label(source.kind)} / {source.source_key}")
        self.detail_url_label.setText(source.url)
        self._set_metric(self.detail_sync_label, self._format_datetime(source.last_sync_at) if source.last_sync_at else self._text("尚未同步", "Never synced"))
        self._set_metric(self.detail_count_label, self._text(f"{total} 个视频", f"{total} videos"))
        self._set_metric(self.detail_pub_label, f"{pub_count}/{total}")
        self._set_metric(self.detail_status_label, self._text("正常", "OK") if source.is_enabled else self._text("已停用", "Disabled"))

        is_video = source.kind is SourceKind.VIDEO
        self.detail_sync_once_button.setEnabled(not is_video and not self._is_syncing)
        self.detail_sync_all_button.setEnabled(not is_video and not self._is_syncing)

    def _show_source_context_menu(self, position) -> None:
        """显示来源列表右键菜单。"""

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication, QMenu

        item = self.source_list.itemAt(position)
        if item is None:
            return
        row_index = self.source_list.row(item)
        self.source_list.setCurrentRow(row_index)
        source = self._selected_source()
        if source is None:
            return

        menu = QMenu(self.source_list)
        rename_action = menu.addAction(self._text("重命名来源", "Rename Source"))
        delete_action = menu.addAction(self._text("删除来源", "Delete Source"))
        sync_once_action = menu.addAction(self._text("同步第一页", "Sync First Page"))
        sync_all_action = menu.addAction(self._text("全量同步", "Full Sync"))
        queue_action = menu.addAction(self._text("加入该来源视频到下载队列", "Queue Source Videos"))
        menu.addSeparator()
        copy_action = menu.addAction(self._text("复制来源链接", "Copy Source URL"))
        open_action = menu.addAction(self._text("打开来源链接", "Open Source URL"))
        if source.kind is SourceKind.VIDEO:
            sync_once_action.setEnabled(False)
            sync_all_action.setEnabled(False)

        selected = menu.exec(self.source_list.viewport().mapToGlobal(position))
        if selected is None:
            return
        if selected is rename_action:
            self._rename_source(source)
        elif selected is delete_action:
            self._delete_source(source)
        elif selected is sync_once_action:
            self._sync_source_once(source)
        elif selected is sync_all_action:
            self._sync_saved_source(source)
        elif selected is queue_action:
            self._queue_source_videos(source)
        elif selected is copy_action:
            QApplication.clipboard().setText(source.url)
            self._set_status_text(self._text("来源链接已复制。", "Source URL copied."))
        elif selected is open_action:
            QDesktopServices.openUrl(QUrl(source.url))

    def _rename_selected_source(self) -> None:
        """重命名当前选中的来源。"""

        source = self._selected_source()
        if source is not None:
            self._rename_source(source)

    def _delete_selected_source(self) -> None:
        """删除当前选中的来源。"""

        source = self._selected_source()
        if source is not None:
            self._delete_source(source)

    def _sync_selected_source_once(self) -> None:
        """同步当前来源第一页。"""

        source = self._selected_source()
        if source is not None:
            self._sync_source_once(source)

    def _sync_selected_source_all(self) -> None:
        """全量同步当前来源。"""

        source = self._selected_source()
        if source is not None:
            self._sync_saved_source(source)

    def _queue_selected_source_videos(self) -> None:
        """把当前来源的视频加入下载队列。"""

        source = self._selected_source()
        if source is not None:
            self._queue_source_videos(source)

    def _rename_source(self, source: SourceRecord) -> None:
        """重命名来源。"""

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
            self._show_feedback(self._text("重命名来源", "Rename Source"), str(exc), level="warning")
            return
        self._set_status_text(self._text(f"来源已重命名为：{updated.display_name}", f"Source renamed to: {updated.display_name}"))
        self._refresh_sources(select_source_id=updated.id)
        if self._after_sync_callback is not None:
            self._after_sync_callback()

    def _delete_source(self, source: SourceRecord) -> None:
        """删除来源和它的本地关联。"""

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
        next_id = self._next_source_id_after_delete(source.id)
        try:
            self.context.source_service.delete_source(source.id)
        except Exception as exc:
            self._show_feedback(self._text("删除来源", "Delete Source"), str(exc), level="warning")
            return
        self._set_status_text(self._text("来源已删除。", "Source deleted."))
        self._refresh_sources(select_source_id=next_id)
        if self._after_sync_callback is not None:
            self._after_sync_callback()

    def _next_source_id_after_delete(self, source_id: int | None) -> int | None:
        """删除后尽量选择相邻来源，减少详情面板跳空。"""

        ids = [source.id for source in self._sources]
        if source_id not in ids:
            return None
        index = ids.index(source_id)
        remaining = [source.id for source in self._sources if source.id != source_id]
        if not remaining:
            return None
        return remaining[min(index, len(remaining) - 1)]

    def _sync_source_once(self, source: SourceRecord) -> None:
        """对已保存来源执行第一页同步。"""

        self._run_sync_with_busy_state(
            source,
            self._text(f"正在同步“{source.display_name}”第一页...", f"Syncing first page of {source.display_name}..."),
            lambda: self._do_sync_source_once(source),
        )

    def _do_sync_source_once(self, source: SourceRecord) -> None:
        """执行已保存来源第一页同步。"""

        if source.kind is SourceKind.FAVORITE:
            try:
                result = self.context.source_service.sync_favorite_once(source.url, source.display_name)
            except Exception as exc:
                self._show_feedback(self._text("同步第一页", "Sync First Page"), str(exc), level="warning")
                return
            self._apply_favorite_sync_result(result, self._text("同步第一页", "Sync First Page"), select_source_id=source.id)
            return
        if source.kind is SourceKind.USER:
            try:
                result = self.context.source_service.sync_user_archive(source.url, source.display_name, max_pages=1)
            except Exception as exc:
                self._show_feedback(self._text("同步第一页", "Sync First Page"), str(exc), level="warning")
                return
            self._apply_source_sync_result(result, self._text("同步第一页", "Sync First Page"), select_source_id=source.id)
            return
        self._show_feedback(
            self._text("同步第一页", "Sync First Page"),
            self._text("单视频来源不需要同步。", "Single video sources do not need syncing."),
            level="warning",
        )

    def _sync_saved_source(self, source: SourceRecord) -> None:
        """按已保存来源类型执行全量同步。"""

        self._run_sync_with_busy_state(
            source,
            self._text(f"正在全量同步“{source.display_name}”...", f"Running full sync for {source.display_name}..."),
            lambda: self._do_sync_saved_source(source),
        )

    def _do_sync_saved_source(self, source: SourceRecord) -> None:
        """执行已保存来源全量同步。"""

        if source.kind is SourceKind.FAVORITE:
            try:
                result = self.context.source_service.sync_favorite_all(source.url, source.display_name)
            except Exception as exc:
                self._show_feedback(self._text("全量同步", "Full Sync"), str(exc), level="warning")
                return
            self._apply_source_sync_result(result, self._text("全量同步", "Full Sync"), select_source_id=source.id)
            return
        if source.kind is SourceKind.USER:
            try:
                result = self.context.source_service.sync_user_archive(source.url, source.display_name)
            except Exception as exc:
                self._show_feedback(self._text("全量同步", "Full Sync"), str(exc), level="warning")
                return
            self._apply_source_sync_result(result, self._text("全量同步", "Full Sync"), select_source_id=source.id)
            return
        self._show_feedback(
            self._text("全量同步", "Full Sync"),
            self._text("单视频来源不需要同步。", "Single video sources do not need syncing."),
            level="warning",
        )

    def _queue_source_videos(self, source: SourceRecord) -> None:
        """把某个来源已同步的视频加入下载队列。"""

        try:
            result = self.context.download_service.queue_source_videos(source_id=source.id, limit=500)
        except Exception as exc:
            self._show_feedback(self._text("下载队列", "Download Queue"), str(exc), level="warning")
            return
        message = self._text(
            result.message,
            f"Queued {result.queued_count} task(s), skipped {result.skipped_count} existing task(s).",
        )
        self._set_status_text(message)
        self._show_feedback(self._text("下载队列", "Download Queue"), message)

    def _pick_user_candidate(self, candidates: tuple[UserProbeCandidate, ...]) -> UserProbeCandidate | None:
        """让用户从候选列表中选择一个 UID 和主页定位结果。"""

        items = [
            self._text(
                f"{candidate.name} | UID={candidate.uid} | 粉丝={candidate.fans or 0}",
                f"{candidate.name} | UID={candidate.uid} | fans={candidate.fans or 0}",
            )
            for candidate in candidates
        ]
        selected_text, accepted = self._input_dialog_class.getItem(
            None,
            self._text("选择目标用户", "Choose A User"),
            self._text("请选择要使用的候选用户：", "Choose the candidate user to use:"),
            items,
            0,
            False,
        )
        if not accepted:
            return None
        selected_index = items.index(selected_text)
        return candidates[selected_index]

    def _apply_user_candidate(self, candidate: UserProbeCandidate) -> None:
        """把选中的候选用户回填到来源草稿区域。"""

        self.kind_combo.setCurrentText(SourceKind.USER.value)
        self.value_input.setText(candidate.uid)
        self.name_input.setText(candidate.name)

        preview = self.context.source_service.preview_source(
            kind=SourceKind.USER,
            raw_value=candidate.uid,
            display_name=candidate.name,
        )
        self.status_label.setText(self._text(f"已选中 UID {candidate.uid}。", f"Selected UID {candidate.uid}."))
        self.preview_label.setText(
            self._text(
                f"解析预览：mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}",
                f"Preview: mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}",
            )
        )
        self.next_step_label.setText(
            self._text(f"下一步说明：主页 {candidate.homepage_url}", f"Next step: homepage {candidate.homepage_url}")
        )

    def _probe_user_with_browser(self, raw_value: str):
        """用户探测统一走浏览器内核，避免再次落回公开 API。"""

        preview = self.context.source_service.preview_source(kind=SourceKind.USER, raw_value=raw_value)
        if self._browser_user_search is None:
            # 这里使用隔离的浏览器 profile，不复用登录页 Cookie。
            self._browser_user_search = BrowserUserSearch(user_agent=self.context.settings.user_agent)

        if preview.resolved_key is not None:
            return self._browser_user_search.inspect_user_homepage(preview.resolved_key)
        return self._browser_user_search.search_users(preview.input_value)

    def _preview_source(self) -> None:
        """预览当前来源输入会被解析成什么结果。"""

        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        try:
            preview = self.context.source_service.preview_source(kind=kind, raw_value=raw_value, display_name=display_name)
        except ValueError as exc:
            message = self._text(f"预览失败：{exc}", f"Preview failed: {exc}")
            self.status_label.setText(message)
            self._show_feedback(self._text("解析来源", "Resolve Source"), message, level="warning")
            return

        self.status_label.setText(self._text("预览成功。", "Preview succeeded."))
        self.preview_label.setText(
            self._text(
                f"解析预览：mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}",
                f"Preview: mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}",
            )
        )
        next_step = self.context.source_service.describe_next_sync_step(preview)
        self.next_step_label.setText(self._text(f"下一步说明：{next_step}", f"Next step: {next_step}"))
        feedback = self._text(
            f"识别成功。\n\n输入模式：{preview.input_mode}\n解析结果：{preview.resolved_key}\n可直接保存：{preview.is_ready_for_save}",
            f"Preview succeeded.\n\nInput mode: {preview.input_mode}\nResolved key: {preview.resolved_key}\nReady to save: {preview.is_ready_for_save}",
        )
        self._show_feedback(self._text("解析来源", "Resolve Source"), feedback)

    def _probe_once(self) -> None:
        """按来源类型执行一次探测，并把结果明确弹出显示。"""

        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()

        try:
            if kind is SourceKind.USER:
                result = self._probe_user_with_browser(raw_value=raw_value)
                details = " | ".join(result.items) if result.items else self._text("无更多信息", "No more details")
                self.live_probe_label.setText(self._text(f"实时探测：{result.message} | {details}", f"Live probe: {result.message} | {details}"))

                if result.success and result.candidates:
                    selected = self._pick_user_candidate(result.candidates)
                    if selected is None:
                        self._show_feedback(
                            self._text("单次探测", "Probe Once"),
                            self._text(
                                "已获取候选用户，但你还没有选择其中一个。",
                                "Candidate users were found, but none was selected yet.",
                            ),
                            level="warning",
                        )
                        return

                    self._apply_user_candidate(selected)
                    self._show_feedback(
                        self._text("单次探测", "Probe Once"),
                        self._text(
                            f"已定位到目标用户。\n\n昵称：{selected.name}\nUID：{selected.uid}\n主页：{selected.homepage_url}",
                            f"Target user selected.\n\nName: {selected.name}\nUID: {selected.uid}\nHomepage: {selected.homepage_url}",
                        ),
                    )
                    return

                self._show_feedback(
                    self._text("单次探测", "Probe Once"),
                    self._text(f"探测完成。\n\n{result.message}\n\n{details}", f"Probe finished.\n\n{result.message}\n\n{details}"),
                )
                return

            if kind is SourceKind.FAVORITE:
                result = self.context.source_service.probe_favorite_input(raw_value=raw_value)
                self.live_probe_label.setText(
                    self._text(
                        f"实时探测：{result.message} | title={result.title} | owner={result.owner_name} | count={result.media_count}",
                        f"Live probe: {result.message} | title={result.title} | owner={result.owner_name} | count={result.media_count}",
                    )
                )
                self._show_feedback(
                    self._text("单次探测", "Probe Once"),
                    self._text(
                        f"探测完成。\n\n标题：{result.title}\n拥有者：{result.owner_name}\n数量：{result.media_count}\n结果：{result.message}",
                        f"Probe finished.\n\nTitle: {result.title}\nOwner: {result.owner_name}\nCount: {result.media_count}\nResult: {result.message}",
                    ),
                )
                return

            self.live_probe_label.setText(
                self._text(
                    "实时探测：单视频当前不需要单独校验，可以直接保存。",
                    "Live probe: single videos do not need a separate probe right now and can be saved directly.",
                )
            )
            self._show_feedback(
                self._text("单次探测", "Probe Once"),
                self._text("单视频来源当前不需要额外探测，可以直接保存。", "Single video sources do not require an extra probe right now and can be saved directly."),
            )
        except ValueError as exc:
            message = self._text(f"实时探测失败：{exc}", f"Live probe failed: {exc}")
            self.live_probe_label.setText(message)
            self._show_feedback(self._text("单次探测", "Probe Once"), message, level="warning")

    def _save_source(self, close_dialog=None) -> None:
        """把来源输入写入数据库，并刷新来源列表。"""

        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        try:
            source_id = self.context.source_service.add_source(kind=kind, raw_value=raw_value, display_name=display_name)
        except ValueError as exc:
            message = self._text(f"保存失败：{exc}", f"Save failed: {exc}")
            self.status_label.setText(message)
            self._show_feedback(self._text("保存来源", "Save Source"), message, level="warning")
            return

        message = self._text(f"来源 #{source_id} 已保存。", f"Source #{source_id} has been saved.")
        self.status_label.setText(message)
        self._refresh_sources(select_source_id=source_id)
        self._show_feedback(self._text("保存来源", "Save Source"), message)
        if close_dialog is not None:
            close_dialog.accept()

    def _apply_favorite_sync_result(self, result, title: str, *, select_source_id: int | None = None) -> None:
        """展示收藏夹第一页同步结果。"""

        self._set_status_text(result.message)
        self._set_probe_text(
            self._text(
                f"同步结果：success={result.success} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}",
                f"Sync result: success={result.success} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}",
            )
        )
        self._refresh_sources(select_source_id=select_source_id or result.source_id)
        if self._after_sync_callback is not None:
            self._after_sync_callback()

        dialog_text = self._text(
            f"{result.message}\n\n同步数量：{result.synced_count}\n新增：{result.new_count}\n更新：{result.updated_count}",
            f"{result.message}\n\nSynced: {result.synced_count}\nNew: {result.new_count}\nUpdated: {result.updated_count}",
        )
        self._show_feedback(title, dialog_text, level="info" if result.success else "warning")

    def _apply_source_sync_result(self, result, title: str, *, select_source_id: int | None = None) -> None:
        """统一展示分页同步结果。"""

        self._set_status_text(result.message)
        self._set_probe_text(
            self._text(
                f"同步结果：success={result.success} | pages={result.page_count} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}",
                f"Sync result: success={result.success} | pages={result.page_count} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}",
            )
        )
        self._refresh_sources(select_source_id=select_source_id or result.source_id)
        if self._after_sync_callback is not None:
            self._after_sync_callback()

        dialog_text = self._text(
            f"{result.message}\n\n页数：{result.page_count}\n同步数量：{result.synced_count}\n新增：{result.new_count}\n更新：{result.updated_count}",
            f"{result.message}\n\nPages: {result.page_count}\nSynced: {result.synced_count}\nNew: {result.new_count}\nUpdated: {result.updated_count}",
        )
        self._show_feedback(title, dialog_text, level="info" if result.success else "warning")

    def _kind_label(self, kind: SourceKind) -> str:
        """把内部来源类型转换成界面标签。"""

        labels = {
            SourceKind.USER: self._text("UP主", "User"),
            SourceKind.FAVORITE: self._text("收藏夹", "Favorite"),
            SourceKind.VIDEO: self._text("单视频", "Video"),
        }
        return labels.get(kind, kind.value)

    @staticmethod
    def _format_datetime(value) -> str:
        """格式化界面中的日期时间。"""

        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d %H:%M")


class _RelayoutListWidget:
    """给来源列表补 show/resize 后的重排回调，避免首次进入页面时 item widget 被裁切。"""

    def __new__(cls, relayout_callback):
        from PySide6.QtWidgets import QListWidget

        class RelayoutListWidget(QListWidget):
            def showEvent(self, event):
                super().showEvent(event)
                relayout_callback()

            def resizeEvent(self, event):
                super().resizeEvent(event)
                relayout_callback()

        return RelayoutListWidget()
