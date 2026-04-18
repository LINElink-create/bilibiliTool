from __future__ import annotations

from collections.abc import Callable

from bilibili_tool.application import AppContext
from bilibili_tool.domain import SourceKind, UserProbeCandidate
from bilibili_tool.infra.browser import BrowserUserSearch


class SourcesPage:
    """来源页面，负责来源预览、探测、保存和收藏夹单页同步。"""

    def __init__(self, context: AppContext) -> None:
        self.context = context
        self.table = None
        self.status_label = None
        self.preview_label = None
        self.next_step_label = None
        self.live_probe_label = None
        self.kind_combo = None
        self.value_input = None
        self.name_input = None
        self._table_item_class = None
        self._message_box_class = None
        self._input_dialog_class = None
        self._after_sync_callback: Callable[[], None] | None = None
        self._browser_user_search: BrowserUserSearch | None = None

    def set_after_sync_callback(self, callback: Callable[[], None]) -> None:
        """注册同步成功后的刷新回调，让资源库页面及时更新。"""

        self._after_sync_callback = callback

    def build(self):
        """构造来源页面，并把预览、探测、保存和同步动作放在一起。"""

        from PySide6.QtWidgets import (
            QComboBox,
            QFormLayout,
            QGroupBox,
            QInputDialog,
            QLabel,
            QLineEdit,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        self._message_box_class = QMessageBox
        self._input_dialog_class = QInputDialog
        language = self.context.settings.ui_language
        self._table_item_class = QTableWidgetItem

        widget = QWidget()
        layout = QVBoxLayout(widget)

        title_label = QLabel("<h3>来源</h3>" if language == "zh-CN" else "<h3>Tracked Sources</h3>")
        intro_label = QLabel(
            "当前阶段支持离线预览、单次探测，以及收藏夹第一页同步到本地资源库。"
            if language == "zh-CN"
            else "This stage supports offline previews, single probes, and syncing the first favorite page into the local library."
        )
        intro_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(intro_label)

        form_group = QGroupBox("来源草稿" if language == "zh-CN" else "Source Draft")
        form_layout = QFormLayout(form_group)

        self.kind_combo = QComboBox()
        self.kind_combo.addItems([kind.value for kind in SourceKind])

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText(
            "输入 UID、用户名、用户主页链接、收藏夹 ID、BV 号或对应链接"
            if language == "zh-CN"
            else "Enter a UID, username, user URL, favorite ID, BV id, or a supported link"
        )

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("可选显示名称" if language == "zh-CN" else "Optional display name")

        preview_button = QPushButton("预览来源" if language == "zh-CN" else "Preview Source")
        preview_button.clicked.connect(self._preview_source)

        probe_button = QPushButton("单次探测" if language == "zh-CN" else "Probe Once")
        probe_button.clicked.connect(self._probe_once)

        add_button = QPushButton("保存来源" if language == "zh-CN" else "Save Source")
        add_button.clicked.connect(self._save_source)

        sync_button = QPushButton("同步收藏夹第一页" if language == "zh-CN" else "Sync Favorite Once")
        sync_button.clicked.connect(self._sync_favorite_once)

        self.status_label = QLabel("准备就绪。" if language == "zh-CN" else "Ready.")
        self.preview_label = QLabel("解析预览：尚未生成。" if language == "zh-CN" else "Preview: not generated yet.")
        self.next_step_label = QLabel("下一步说明：尚未生成。" if language == "zh-CN" else "Next step: not generated yet.")
        self.live_probe_label = QLabel("实时探测：尚未执行。" if language == "zh-CN" else "Live probe: not executed yet.")
        for label in (self.status_label, self.preview_label, self.next_step_label, self.live_probe_label):
            label.setWordWrap(True)

        form_layout.addRow("类型" if language == "zh-CN" else "Kind", self.kind_combo)
        form_layout.addRow("输入值" if language == "zh-CN" else "Value", self.value_input)
        form_layout.addRow("显示名称" if language == "zh-CN" else "Display Name", self.name_input)
        form_layout.addRow(preview_button)
        form_layout.addRow(probe_button)
        form_layout.addRow(add_button)
        form_layout.addRow(sync_button)
        form_layout.addRow("状态" if language == "zh-CN" else "Status", self.status_label)
        form_layout.addRow("预览" if language == "zh-CN" else "Preview", self.preview_label)
        form_layout.addRow("下一步" if language == "zh-CN" else "Next Step", self.next_step_label)
        form_layout.addRow("探测结果" if language == "zh-CN" else "Probe Result", self.live_probe_label)
        layout.addWidget(form_group)

        self.table = QTableWidget(0, 5)
        headers = ["ID", "类型", "名称", "链接", "最后同步"] if language == "zh-CN" else ["ID", "Kind", "Name", "URL", "Last Sync"]
        self.table.setHorizontalHeaderLabels(headers)
        layout.addWidget(self.table)

        self._refresh_table()
        return widget

    def _show_feedback(self, title: str, message: str, level: str = "info") -> None:
        """弹出更明确的结果提示，避免按钮动作看起来像没反应。"""

        box = self._message_box_class
        if level == "error":
            box.critical(None, title, message)
        elif level == "warning":
            box.warning(None, title, message)
        else:
            box.information(None, title, message)

    def _pick_user_candidate(self, candidates: tuple[UserProbeCandidate, ...]) -> UserProbeCandidate | None:
        """让用户从候选列表中选择一个 UID 和主页定位结果。"""

        language = self.context.settings.ui_language
        items = [
            (
                f"{candidate.name} | UID={candidate.uid} | 粉丝={candidate.fans or 0}"
                if language == "zh-CN"
                else f"{candidate.name} | UID={candidate.uid} | fans={candidate.fans or 0}"
            )
            for candidate in candidates
        ]
        title = "选择目标用户" if language == "zh-CN" else "Choose A User"
        label = "请选择要使用的候选用户：" if language == "zh-CN" else "Choose the candidate user to use:"
        selected_text, accepted = self._input_dialog_class.getItem(None, title, label, items, 0, False)
        if not accepted:
            return None
        selected_index = items.index(selected_text)
        return candidates[selected_index]

    def _apply_user_candidate(self, candidate: UserProbeCandidate) -> None:
        """把选中的候选用户回填到来源草稿区域。"""

        language = self.context.settings.ui_language
        self.kind_combo.setCurrentText(SourceKind.USER.value)
        self.value_input.setText(candidate.uid)
        self.name_input.setText(candidate.name)

        preview = self.context.source_service.preview_source(
            kind=SourceKind.USER,
            raw_value=candidate.uid,
            display_name=candidate.name,
        )
        self.status_label.setText(
            f"已选中 UID {candidate.uid}。"
            if language == "zh-CN"
            else f"Selected UID {candidate.uid}."
        )
        self.preview_label.setText(
            f"解析预览：mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}"
            if language == "zh-CN"
            else f"Preview: mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}"
        )
        self.next_step_label.setText(
            f"下一步说明：主页 {candidate.homepage_url}"
            if language == "zh-CN"
            else f"Next step: homepage {candidate.homepage_url}"
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

        language = self.context.settings.ui_language
        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        try:
            preview = self.context.source_service.preview_source(kind=kind, raw_value=raw_value, display_name=display_name)
        except ValueError as exc:
            message = f"预览失败：{exc}" if language == "zh-CN" else f"Preview failed: {exc}"
            self.status_label.setText(message)
            self._show_feedback("预览来源" if language == "zh-CN" else "Preview Source", message, level="warning")
            return

        self.status_label.setText("预览成功。" if language == "zh-CN" else "Preview succeeded.")
        self.preview_label.setText(
            f"解析预览：mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}"
            if language == "zh-CN"
            else f"Preview: mode={preview.input_mode} | key={preview.resolved_key} | ready={preview.is_ready_for_save}"
        )
        next_step = self.context.source_service.describe_next_sync_step(preview)
        self.next_step_label.setText(
            f"下一步说明：{next_step}" if language == "zh-CN" else f"Next step: {next_step}"
        )
        feedback = (
            f"识别成功。\n\n输入模式：{preview.input_mode}\n解析结果：{preview.resolved_key}\n可直接保存：{preview.is_ready_for_save}"
            if language == "zh-CN"
            else f"Preview succeeded.\n\nInput mode: {preview.input_mode}\nResolved key: {preview.resolved_key}\nReady to save: {preview.is_ready_for_save}"
        )
        self._show_feedback("预览来源" if language == "zh-CN" else "Preview Source", feedback)

    def _probe_once(self) -> None:
        """按来源类型执行一次探测，并把结果明确弹出显示。"""

        language = self.context.settings.ui_language
        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()

        try:
            if kind is SourceKind.USER:
                result = self._probe_user_with_browser(raw_value=raw_value)
                details = " | ".join(result.items) if result.items else ("无更多信息" if language == "zh-CN" else "No more details")
                label_text = (
                    f"实时探测：{result.message} | {details}"
                    if language == "zh-CN"
                    else f"Live probe: {result.message} | {details}"
                )
                self.live_probe_label.setText(label_text)

                if result.success and result.candidates:
                    selected = self._pick_user_candidate(result.candidates)
                    if selected is None:
                        self._show_feedback(
                            "单次探测" if language == "zh-CN" else "Probe Once",
                            "已获取候选用户，但你还没有选择其中一个。"
                            if language == "zh-CN"
                            else "Candidate users were found, but none was selected yet.",
                            level="warning",
                        )
                        return

                    self._apply_user_candidate(selected)
                    dialog_text = (
                        f"已定位到目标用户。\n\n昵称：{selected.name}\nUID：{selected.uid}\n主页：{selected.homepage_url}"
                        if language == "zh-CN"
                        else f"Target user selected.\n\nName: {selected.name}\nUID: {selected.uid}\nHomepage: {selected.homepage_url}"
                    )
                    self._show_feedback("单次探测" if language == "zh-CN" else "Probe Once", dialog_text)
                    return

                dialog_text = (
                    f"探测完成。\n\n{result.message}\n\n{details}"
                    if language == "zh-CN"
                    else f"Probe finished.\n\n{result.message}\n\n{details}"
                )
                self._show_feedback("单次探测" if language == "zh-CN" else "Probe Once", dialog_text)
                return

            if kind is SourceKind.FAVORITE:
                result = self.context.source_service.probe_favorite_input(raw_value=raw_value)
                label_text = (
                    f"实时探测：{result.message} | title={result.title} | owner={result.owner_name} | count={result.media_count}"
                    if language == "zh-CN"
                    else f"Live probe: {result.message} | title={result.title} | owner={result.owner_name} | count={result.media_count}"
                )
                self.live_probe_label.setText(label_text)
                dialog_text = (
                    f"探测完成。\n\n标题：{result.title}\n拥有者：{result.owner_name}\n数量：{result.media_count}\n结果：{result.message}"
                    if language == "zh-CN"
                    else f"Probe finished.\n\nTitle: {result.title}\nOwner: {result.owner_name}\nCount: {result.media_count}\nResult: {result.message}"
                )
                self._show_feedback("单次探测" if language == "zh-CN" else "Probe Once", dialog_text)
                return

            self.live_probe_label.setText(
                "实时探测：单视频当前不需要单独校验，可以直接保存。"
                if language == "zh-CN"
                else "Live probe: single videos do not need a separate probe right now and can be saved directly."
            )
            dialog_text = (
                "单视频来源当前不需要额外探测，可以直接保存。"
                if language == "zh-CN"
                else "Single video sources do not require an extra probe right now and can be saved directly."
            )
            self._show_feedback("单次探测" if language == "zh-CN" else "Probe Once", dialog_text)
        except ValueError as exc:
            message = f"实时探测失败：{exc}" if language == "zh-CN" else f"Live probe failed: {exc}"
            self.live_probe_label.setText(message)
            self._show_feedback("单次探测" if language == "zh-CN" else "Probe Once", message, level="warning")

    def _save_source(self) -> None:
        """把来源输入写入数据库，并刷新表格。"""

        language = self.context.settings.ui_language
        kind = SourceKind(self.kind_combo.currentText())
        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        try:
            source_id = self.context.source_service.add_source(kind=kind, raw_value=raw_value, display_name=display_name)
        except ValueError as exc:
            message = f"保存失败：{exc}" if language == "zh-CN" else f"Save failed: {exc}"
            self.status_label.setText(message)
            self._show_feedback("保存来源" if language == "zh-CN" else "Save Source", message, level="warning")
            return

        message = (
            f"来源 #{source_id} 已保存。"
            if language == "zh-CN"
            else f"Source #{source_id} has been saved."
        )
        self.status_label.setText(message)
        self._refresh_table()
        self._show_feedback("保存来源" if language == "zh-CN" else "Save Source", message)

    def _sync_favorite_once(self) -> None:
        """把当前收藏夹第一页同步进本地资源库。"""

        language = self.context.settings.ui_language
        kind = SourceKind(self.kind_combo.currentText())
        if kind is not SourceKind.FAVORITE:
            message = (
                "当前按钮只支持收藏夹来源。"
                if language == "zh-CN"
                else "This button only supports favorite sources."
            )
            self.status_label.setText(message)
            self._show_feedback("同步收藏夹第一页" if language == "zh-CN" else "Sync Favorite Once", message, level="warning")
            return

        raw_value = self.value_input.text().strip()
        display_name = self.name_input.text().strip() or None

        try:
            result = self.context.source_service.sync_favorite_once(raw_value=raw_value, display_name=display_name)
        except ValueError as exc:
            message = f"同步失败：{exc}" if language == "zh-CN" else f"Sync failed: {exc}"
            self.status_label.setText(message)
            self._show_feedback("同步收藏夹第一页" if language == "zh-CN" else "Sync Favorite Once", message, level="warning")
            return

        self.status_label.setText(result.message)
        self.live_probe_label.setText(
            f"同步结果：success={result.success} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}"
            if language == "zh-CN"
            else f"Sync result: success={result.success} | synced={result.synced_count} | new={result.new_count} | updated={result.updated_count}"
        )
        self._refresh_table()
        if self._after_sync_callback is not None:
            self._after_sync_callback()

        dialog_text = (
            f"{result.message}\n\n同步数量：{result.synced_count}\n新增：{result.new_count}\n更新：{result.updated_count}"
            if language == "zh-CN"
            else f"{result.message}\n\nSynced: {result.synced_count}\nNew: {result.new_count}\nUpdated: {result.updated_count}"
        )
        self._show_feedback("同步收藏夹第一页" if language == "zh-CN" else "Sync Favorite Once", dialog_text)

    def _refresh_table(self) -> None:
        """重新加载来源列表，让页面状态和数据库保持同步。"""

        table_item = self._table_item_class
        sources = self.context.source_service.list_sources()
        self.table.setRowCount(len(sources))
        for row_index, source in enumerate(sources):
            self.table.setItem(row_index, 0, table_item(str(source.id)))
            self.table.setItem(row_index, 1, table_item(source.kind.value))
            self.table.setItem(row_index, 2, table_item(source.display_name))
            self.table.setItem(row_index, 3, table_item(source.url))
            self.table.setItem(row_index, 4, table_item(source.last_sync_at.isoformat(sep=" ") if source.last_sync_at else "-"))
