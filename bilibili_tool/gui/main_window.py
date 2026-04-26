from __future__ import annotations

from PySide6.QtCore import QObject

from bilibili_tool.application import AppContext
from bilibili_tool.gui.i18n import t
from bilibili_tool.gui.pages import DashboardPage, DownloadsPage, LibraryPage, LoginPage, SettingsPage, SourcesPage
from bilibili_tool.gui.theme import app_stylesheet


class MainWindow(QObject):
    """构建桌面主窗口，使用自定义顶部导航替代默认标签页。"""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.window = None
        self.stack = None
        self.nav_buttons = []
        self.page_controllers = []
        self.page_widgets = []
        self._page_defs = []
        self._current_page_index = None
        self._rebuilt_window = None
        self._rebuilt_controller = None
        self._drag_position = None
        self.maximize_button = None

    def build(self):
        """创建主窗口和固定顶部导航。"""

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(app_stylesheet())

        window = QMainWindow()
        window.setWindowTitle("bilibiliTool")
        window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        window.resize(1280, 850)

        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_nav = QFrame()
        top_nav.setObjectName("topNav")
        top_nav.installEventFilter(self)
        top_layout = QHBoxLayout(top_nav)
        top_layout.setContentsMargins(10, 0, 8, 0)
        top_layout.setSpacing(4)

        icon_factory = _LineIconFactory()
        brand_icon = QLabel()
        brand_icon.setObjectName("brandIcon")
        brand_icon.setPixmap(icon_factory.pixmap("brand", 20, "#2288b8"))
        brand_icon.installEventFilter(self)
        brand_text = QLabel("bilibiliTool")
        brand_text.setObjectName("brandText")
        brand_text.installEventFilter(self)
        top_layout.addWidget(brand_icon)
        top_layout.addWidget(brand_text)
        top_layout.addSpacing(24)

        language = self.context.settings.ui_language
        sources_page = SourcesPage(self.context)
        library_page = LibraryPage(self.context)
        downloads_page = DownloadsPage(self.context)
        login_page = LoginPage(self.context)
        settings_page = SettingsPage(self.context, on_language_changed=self._handle_language_changed)
        dashboard_page = DashboardPage(
            self.context,
            on_new_source=lambda: self._open_new_source_from_dashboard(sources_page),
            on_open_library=lambda: self._switch_page(2),
            on_open_downloads=lambda: self._switch_page(3),
        )
        self.page_controllers = [
            dashboard_page,
            sources_page,
            library_page,
            downloads_page,
            login_page,
            settings_page,
        ]

        sources_page.set_after_sync_callback(lambda: library_page.refresh() if library_page.table is not None else None)

        self.stack = QStackedWidget()
        self._page_defs = [
            (t(language, "nav.dashboard"), icon_factory.icon("home"), dashboard_page),
            (t(language, "nav.sources"), icon_factory.icon("source"), sources_page),
            (t(language, "nav.library"), icon_factory.icon("library"), library_page),
            (t(language, "nav.downloads"), icon_factory.icon("download"), downloads_page),
            (t(language, "nav.login"), icon_factory.icon("login"), login_page),
            (t(language, "nav.settings"), icon_factory.icon("settings"), settings_page),
        ]

        self.nav_buttons = []
        self.page_widgets = []
        for index, (label, icon, _controller) in enumerate(self._page_defs):
            button = QPushButton(label)
            button.setIcon(icon)
            button.setObjectName("navButton")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page_index=index: self._switch_page(page_index))
            top_layout.addWidget(button)
            self.nav_buttons.append(button)
            placeholder = QWidget()
            placeholder.setObjectName("pageRoot")
            self.page_widgets.append(None)
            self.stack.addWidget(placeholder)

        top_layout.addStretch(1)
        minimize_button = QPushButton()
        minimize_button.setIcon(icon_factory.icon("minimize"))
        minimize_button.setObjectName("titleButton")
        minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button = QPushButton()
        self.maximize_button.setIcon(icon_factory.icon("maximize"))
        self.maximize_button.setObjectName("titleButton")
        self.maximize_button.clicked.connect(self._toggle_maximized)
        close_button = QPushButton()
        close_button.setIcon(icon_factory.icon("close"))
        close_button.setObjectName("titleCloseButton")
        close_button.clicked.connect(window.close)
        for button in (minimize_button, self.maximize_button, close_button):
            button.setFixedSize(42, 32)
            top_layout.addWidget(button)
        root_layout.addWidget(top_nav)
        root_layout.addWidget(self.stack, 1)
        window.setCentralWidget(root)

        self.window = window
        window._bilibili_tool_controller = self
        self._switch_page(0)
        return window

    def eventFilter(self, watched, event) -> bool:
        """支持自定义标题栏拖拽和双击最大化。"""

        from PySide6.QtCore import QEvent, Qt

        if self.window is None:
            return False
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            self._toggle_maximized()
            return True
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            return True
        if event.type() == QEvent.MouseMove and self._drag_position is not None and event.buttons() & Qt.LeftButton:
            if self.window.isMaximized():
                return True
            self.window.move(event.globalPosition().toPoint() - self._drag_position)
            return True
        if event.type() == QEvent.MouseButtonRelease:
            self._drag_position = None
            return True
        return False

    def _toggle_maximized(self) -> None:
        """切换最大化/还原，并同步标题栏按钮文案。"""

        if self.window is None:
            return
        if self.window.isMaximized():
            self.window.showNormal()
            if self.maximize_button is not None:
                self.maximize_button.setIcon(_LineIconFactory().icon("maximize"))
        else:
            self.window.showMaximized()
            if self.maximize_button is not None:
                self.maximize_button.setIcon(_LineIconFactory().icon("restore"))

    def _switch_page(self, index: int) -> None:
        """切换页面并刷新顶部导航的蓝色下划线状态。"""

        if self.stack is None:
            return
        if self._current_page_index is not None and self._current_page_index != index:
            self._notify_page_visibility(self._current_page_index, visible=False)
        self._ensure_page_built(index)
        self.stack.setCurrentIndex(index)
        self._current_page_index = index
        self._notify_page_visibility(index, visible=True)
        for button_index, button in enumerate(self.nav_buttons):
            button.setProperty("active", "true" if button_index == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _ensure_page_built(self, index: int) -> None:
        """首次进入页面时才构建真实页面，降低启动和切换时的同步负担。"""

        if self.stack is None or self.page_widgets[index] is not None:
            return
        controller = self._page_defs[index][2]
        page_widget = controller.build()
        placeholder = self.stack.widget(index)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, page_widget)
        self.page_widgets[index] = page_widget

    def _notify_page_visibility(self, index: int, *, visible: bool) -> None:
        """把页面可见性通知给控制器，让重页面能暂停后台刷新。"""

        if index < 0 or index >= len(self.page_controllers):
            return
        controller = self.page_controllers[index]
        method_name = "on_page_shown" if visible else "on_page_hidden"
        handler = getattr(controller, method_name, None)
        if handler is not None:
            handler()

    def _open_new_source_from_dashboard(self, sources_page: SourcesPage) -> None:
        """首页快捷入口：先切到来源页，再打开新建来源弹窗。"""

        from PySide6.QtCore import QTimer

        self._switch_page(1)
        QTimer.singleShot(0, sources_page._open_source_dialog)

    def _handle_language_changed(self) -> None:
        """语言切换后重建主窗口，保证导航和页面文案同步。"""

        if self.window is None:
            return
        old_window = self.window
        controller = MainWindow(self.context)
        rebuilt = controller.build()
        self._rebuilt_controller = controller
        self._rebuilt_window = rebuilt
        rebuilt.show()
        old_window.close()


def run_desktop_app(context: AppContext) -> int:
    """启动 PySide6 桌面应用。"""

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    controller = MainWindow(context)
    window = controller.build()
    window._bilibili_tool_controller = controller
    window.show()
    return app.exec()


class _LineIconFactory:
    """用 QPainter 绘制一组轻量线性图标，避免系统默认彩色图标破坏统一风格。"""

    def icon(self, name: str):
        """返回指定图标的 QIcon。"""

        from PySide6.QtGui import QIcon

        return QIcon(self.pixmap(name, 18, "#1f3447"))

    def pixmap(self, name: str, size: int, color: str):
        """绘制指定名称的线性图标。"""

        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), max(1.4, size / 13))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        s = float(size)

        if name == "brand":
            painter.drawRoundedRect(QRectF(s * 0.18, s * 0.28, s * 0.64, s * 0.48), 3, 3)
            painter.drawLine(QPointF(s * 0.34, s * 0.28), QPointF(s * 0.26, s * 0.16))
            painter.drawLine(QPointF(s * 0.66, s * 0.28), QPointF(s * 0.74, s * 0.16))
            painter.drawPoint(QPointF(s * 0.38, s * 0.50))
            painter.drawPoint(QPointF(s * 0.62, s * 0.50))
            painter.drawLine(QPointF(s * 0.42, s * 0.64), QPointF(s * 0.58, s * 0.64))
        elif name == "home":
            painter.drawPolyline([QPointF(s * 0.18, s * 0.50), QPointF(s * 0.50, s * 0.22), QPointF(s * 0.82, s * 0.50)])
            painter.drawRect(QRectF(s * 0.28, s * 0.48, s * 0.44, s * 0.34))
        elif name == "source":
            painter.drawRoundedRect(QRectF(s * 0.16, s * 0.30, s * 0.68, s * 0.46), 2, 2)
            painter.drawLine(QPointF(s * 0.22, s * 0.30), QPointF(s * 0.38, s * 0.20))
            painter.drawLine(QPointF(s * 0.38, s * 0.20), QPointF(s * 0.54, s * 0.30))
            painter.drawLine(QPointF(s * 0.50, s * 0.42), QPointF(s * 0.50, s * 0.66))
            painter.drawLine(QPointF(s * 0.38, s * 0.54), QPointF(s * 0.62, s * 0.54))
        elif name == "library":
            for x in (0.22, 0.44, 0.66):
                painter.drawRoundedRect(QRectF(s * x, s * 0.24, s * 0.12, s * 0.52), 1.5, 1.5)
        elif name == "download":
            painter.drawLine(QPointF(s * 0.50, s * 0.18), QPointF(s * 0.50, s * 0.62))
            painter.drawPolyline([QPointF(s * 0.32, s * 0.46), QPointF(s * 0.50, s * 0.64), QPointF(s * 0.68, s * 0.46)])
            painter.drawLine(QPointF(s * 0.24, s * 0.78), QPointF(s * 0.76, s * 0.78))
        elif name == "login":
            painter.drawEllipse(QRectF(s * 0.36, s * 0.18, s * 0.28, s * 0.28))
            painter.drawArc(QRectF(s * 0.24, s * 0.48, s * 0.52, s * 0.42), 20 * 16, 140 * 16)
        elif name == "settings":
            painter.drawEllipse(QRectF(s * 0.35, s * 0.35, s * 0.30, s * 0.30))
            for start, end in (
                ((0.50, 0.12), (0.50, 0.26)),
                ((0.50, 0.74), (0.50, 0.88)),
                ((0.12, 0.50), (0.26, 0.50)),
                ((0.74, 0.50), (0.88, 0.50)),
                ((0.23, 0.23), (0.32, 0.32)),
                ((0.68, 0.68), (0.77, 0.77)),
                ((0.77, 0.23), (0.68, 0.32)),
                ((0.32, 0.68), (0.23, 0.77)),
            ):
                painter.drawLine(QPointF(s * start[0], s * start[1]), QPointF(s * end[0], s * end[1]))
        elif name == "minimize":
            painter.drawLine(QPointF(s * 0.28, s * 0.58), QPointF(s * 0.72, s * 0.58))
        elif name == "maximize":
            painter.drawRect(QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40))
        elif name == "restore":
            painter.drawRect(QRectF(s * 0.24, s * 0.36, s * 0.34, s * 0.34))
            painter.drawRect(QRectF(s * 0.42, s * 0.22, s * 0.34, s * 0.34))
        elif name == "close":
            painter.drawLine(QPointF(s * 0.32, s * 0.32), QPointF(s * 0.68, s * 0.68))
            painter.drawLine(QPointF(s * 0.68, s * 0.32), QPointF(s * 0.32, s * 0.68))

        painter.end()
        return pixmap
