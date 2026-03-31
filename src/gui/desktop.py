from __future__ import annotations

from src.services.application import AppContext


def run_desktop_app(context: AppContext) -> int:
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget
    except ImportError:
        print("PySide6 is not installed. Install requirements and run again to launch the desktop shell.")
        return 1

    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("bilibiliTool v1")
    window.resize(1100, 720)

    tabs = QTabWidget()
    tabs.addTab(_build_placeholder_tab("Crawler", "Import by UID or URL and queue videos into the library."), "抓取")
    tabs.addTab(_build_placeholder_tab("Downloads", "Track yt-dlp tasks and output files here."), "下载")
    tabs.addTab(_build_placeholder_tab("Library", _library_summary(context)), "媒体库")
    window.setCentralWidget(tabs)
    window.show()
    return app.exec()


def _build_placeholder_tab(title: str, body: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel(f"<h2>{title}</h2><p>{body}</p>"))
    return widget


def _library_summary(context: AppContext) -> str:
    count = len(context.repository.list_videos(limit=10))
    return f"Database ready. Latest cached videos visible in the CLI: {count}."
