from __future__ import annotations

from bilibili_tool.config import SUPPORTED_UI_LANGUAGES, normalize_ui_language


LANGUAGE_LABELS = {
    "zh-CN": "简体中文",
    "en-US": "English",
}


TRANSLATIONS = {
    "app.title": {
        "zh-CN": "bilibiliTool",
        "en-US": "bilibiliTool",
    },
    "nav.dashboard": {
        "zh-CN": "首页",
        "en-US": "Dashboard",
    },
    "nav.sources": {
        "zh-CN": "来源",
        "en-US": "Sources",
    },
    "nav.library": {
        "zh-CN": "资源库",
        "en-US": "Library",
    },
    "nav.downloads": {
        "zh-CN": "下载",
        "en-US": "Downloads",
    },
    "nav.login": {
        "zh-CN": "登录",
        "en-US": "Login",
    },
    "nav.settings": {
        "zh-CN": "设置",
        "en-US": "Settings",
    },
    "settings.title": {
        "zh-CN": "设置",
        "en-US": "Settings",
    },
    "settings.language_group": {
        "zh-CN": "界面语言",
        "en-US": "Interface Language",
    },
    "settings.language_label": {
        "zh-CN": "语言",
        "en-US": "Language",
    },
    "settings.language_help": {
        "zh-CN": "启动时会优先读取本地保存的语言设置；如果没有，再根据系统语言自动选择。",
        "en-US": "The app first loads the saved local language setting. If none exists, it falls back to the system language.",
    },
    "settings.save_language": {
        "zh-CN": "保存语言设置",
        "en-US": "Save Language Setting",
    },
    "settings.status_saved": {
        "zh-CN": "语言设置已保存，界面已切换。",
        "en-US": "Language setting saved and the UI has been updated.",
    },
    "settings.current_language": {
        "zh-CN": "当前语言：{value}",
        "en-US": "Current language: {value}",
    },
}


def t(language: str, key: str, **kwargs: object) -> str:
    """根据当前语言返回对应文案。"""

    normalized = normalize_ui_language(language)
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key.format(**kwargs) if kwargs else key
    template = entry.get(normalized) or entry.get("zh-CN") or key
    return template.format(**kwargs)


def language_display_name(language: str) -> str:
    """返回语言代码对应的人类可读名称。"""

    return LANGUAGE_LABELS.get(normalize_ui_language(language), LANGUAGE_LABELS["zh-CN"])


def language_options() -> list[tuple[str, str]]:
    """返回可供界面使用的语言选项。"""

    return [(language, LANGUAGE_LABELS[language]) for language in SUPPORTED_UI_LANGUAGES]
