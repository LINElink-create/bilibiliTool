from __future__ import annotations


def app_stylesheet() -> str:
    """返回全局桌面主题样式，让所有页面保持和来源页一致的视觉语言。"""

    return """
    QMainWindow, QWidget#appRoot, QWidget#pageRoot {
        background: #f6f3ec;
        color: #1f2933;
        font-family: "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI";
        font-size: 13px;
    }
    QFrame#topNav {
        background: #fffdf8;
        border-bottom: 1px solid #ded8cb;
        min-height: 38px;
        max-height: 38px;
    }
    QLabel#brandIcon {
        color: #2288b8;
        font-size: 18px;
        font-weight: 800;
    }
    QLabel#brandText {
        color: #1f2933;
        font-weight: 700;
    }
    QPushButton#navButton {
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        color: #344054;
        padding: 10px 18px 8px 18px;
        font-weight: 600;
    }
    QPushButton#navButton:hover {
        color: #176d8f;
        background: #f3f9fc;
    }
    QPushButton#navButton[active="true"] {
        color: #1570b8;
        border-bottom-color: #2288e8;
        background: #fffdf8;
    }
    QPushButton#titleButton, QPushButton#titleCloseButton {
        background: transparent;
        border: none;
        border-radius: 0;
        color: #344054;
        font-size: 14px;
        font-weight: 600;
        padding: 0;
    }
    QPushButton#titleButton:hover {
        background: #edf4f7;
    }
    QPushButton#titleCloseButton:hover {
        background: #fcebea;
        color: #b42318;
    }
    #pageTitle {
        font-size: 22px;
        font-weight: 800;
        color: #172536;
    }
    #pageSubtitle, #mutedText {
        color: #667085;
        font-size: 12px;
    }
    QFrame#card, QFrame#sourceCard, QFrame#metricCard, QFrame#actionBox,
    QFrame#statusPanel, QFrame#dialogBody, QGroupBox#cardGroup {
        background: #fffdf8;
        border: 1px solid #ded8cb;
        border-radius: 14px;
    }
    QGroupBox#cardGroup {
        margin-top: 12px;
        padding-top: 14px;
        font-weight: 700;
        color: #1e3448;
    }
    QGroupBox#cardGroup::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
        background: #f6f3ec;
    }
    #sectionTitle {
        font-size: 15px;
        font-weight: 800;
        color: #1e3448;
    }
    #metricTitle {
        color: #7a8694;
        font-size: 12px;
    }
    #metricValue {
        color: #172536;
        font-size: 20px;
        font-weight: 800;
    }
    QFrame#dashboardHero, QFrame#dashboardSection, QFrame#dashboardMetric,
    QFrame#quickAction, QFrame#quickActionPrimary {
        background: #fffdf8;
        border: 1px solid #e2d9c9;
        border-radius: 14px;
    }
    QFrame#dashboardHero {
        background: #fffdfa;
    }
    QFrame#dashboardSection {
        background: #fffefa;
    }
    QFrame#dashboardMetric {
        background: #ffffff;
        border-color: #e7dfd2;
    }
    QFrame#dashboardMetric[accent="true"] {
        background: #f7fbff;
        border-color: #c9e3f5;
    }
    #heroTitle {
        color: #10233b;
        font-size: 17px;
        font-weight: 900;
    }
    #metricDelta {
        color: #728094;
        font-size: 11px;
    }
    QFrame#quickAction {
        background: #f7fbff;
        border-color: #cfe6f4;
        min-height: 112px;
    }
    QFrame#quickActionPrimary {
        background: #eef8ff;
        border-color: #b7ddf5;
        min-height: 112px;
    }
    QFrame#quickAction:hover, QFrame#quickActionPrimary:hover {
        background: #eaf6fd;
        border-color: #8ec5e8;
    }
    #quickActionIcon {
        background: #ffffff;
        border: 1px solid #b7ddf5;
        border-radius: 11px;
        color: #1570b8;
        font-size: 17px;
        font-weight: 900;
        min-width: 32px;
        min-height: 32px;
        max-width: 32px;
        max-height: 32px;
    }
    #quickActionTitle {
        color: #126897;
        font-weight: 900;
    }
    #quickActionSubtitle {
        color: #6b7788;
        font-size: 11px;
    }
    QFrame#activityRow {
        background: transparent;
        border: none;
    }
    #activityText {
        color: #27384b;
        font-size: 12px;
    }
    #activityTime {
        color: #8a95a5;
        font-size: 11px;
    }
    #activityDot_source, #activityDot_download, #activityDot_warning {
        border-radius: 10px;
        min-width: 20px;
        min-height: 20px;
        max-width: 20px;
        max-height: 20px;
        font-size: 11px;
        font-weight: 900;
    }
    #activityDot_source {
        color: #1570b8;
        background: #e8f4ff;
        border: 1px solid #b7ddf5;
    }
    #activityDot_download {
        color: #16845b;
        background: #eaf8ef;
        border: 1px solid #bfe8d0;
    }
    #activityDot_warning {
        color: #b54708;
        background: #fff4e5;
        border: 1px solid #fed7aa;
    }
    QPushButton {
        background: #ffffff;
        border: 1px solid #cfd8df;
        border-radius: 9px;
        padding: 7px 12px;
        color: #1f3447;
        font-weight: 600;
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
    QPushButton#primaryButton {
        background: #2288b8;
        border-color: #1f7fae;
        color: white;
        font-weight: 800;
    }
    QPushButton#primaryButton:hover {
        background: #1b78a5;
    }
    QPushButton#softButton {
        background: #eef7fb;
        border-color: #b9ddea;
        color: #176d8f;
        font-weight: 800;
    }
    QPushButton#dangerButton {
        color: #b42318;
        border-color: #f0b8b2;
        background: #fff7f6;
    }
    QLineEdit, QComboBox, QSpinBox {
        background: #fffefa;
        border: 1px solid #cfd8df;
        border-radius: 9px;
        padding: 6px 9px;
        min-height: 26px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border-color: #2288b8;
    }
    QTableWidget {
        background: #ffffff;
        alternate-background-color: #f8fafb;
        border: 1px solid #e8e2d7;
        border-radius: 10px;
        gridline-color: #e5e7eb;
        selection-background-color: #dff1fb;
        selection-color: #172536;
    }
    QHeaderView::section {
        background: #f4f8fa;
        border: none;
        border-right: 1px solid #e3e9ed;
        border-bottom: 1px solid #dbe5ea;
        padding: 7px;
        color: #344054;
        font-weight: 800;
    }
    QListWidget {
        background: transparent;
        border: none;
        outline: 0;
    }
    QListWidget::item {
        border-radius: 10px;
        padding: 8px;
        margin: 2px 0;
    }
    QListWidget::item:selected {
        background: #eaf5ff;
        color: #172536;
    }
    #statusPill {
        background: #edf7f9;
        color: #15708a;
        border: 1px solid #bee1ea;
        border-radius: 9px;
        padding: 3px 8px;
        font-weight: 700;
    }
    QProgressBar {
        min-height: 8px;
        max-height: 12px;
        border: 1px solid #b9ddea;
        border-radius: 5px;
        background: #eef7fb;
        text-align: center;
    }
    QProgressBar::chunk {
        border-radius: 5px;
        background: #2288b8;
    }
    QProgressBar#downloadTaskProgress {
        min-height: 20px;
        max-height: 20px;
        border-radius: 9px;
        color: #10233b;
        font-size: 11px;
        font-weight: 700;
        background: #e9f4fb;
        border: 1px solid #c2deee;
        text-align: center;
    }
    QProgressBar#downloadTaskProgress::chunk {
        border-radius: 8px;
        background: #258fbd;
    }
    """


def page_root():
    """创建统一页面根容器，供各页面复用背景和边距。"""

    from PySide6.QtWidgets import QVBoxLayout, QWidget

    widget = QWidget()
    widget.setObjectName("pageRoot")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(14)
    return widget, layout


def card_frame(object_name: str = "card"):
    """创建统一圆角卡片容器。"""

    from PySide6.QtWidgets import QFrame

    frame = QFrame()
    frame.setObjectName(object_name)
    return frame


def metric_card(title: str, value: str, subtitle: str | None = None):
    """创建首页和详情页通用的指标卡片。"""

    from PySide6.QtWidgets import QLabel, QVBoxLayout

    card = card_frame("metricCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setObjectName("metricTitle")
    value_label = QLabel(value)
    value_label.setObjectName("metricValue")
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("mutedText")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    return card
