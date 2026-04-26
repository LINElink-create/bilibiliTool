"""Configuration helpers for bilibiliTool."""

from bilibili_tool.config.paths import AppPaths, build_app_paths
from bilibili_tool.config.settings import (
    SUPPORTED_UI_LANGUAGES,
    AppSettings,
    detect_system_language,
    load_settings,
    normalize_ui_language,
    save_settings,
)

__all__ = [
    "AppPaths",
    "AppSettings",
    "SUPPORTED_UI_LANGUAGES",
    "build_app_paths",
    "detect_system_language",
    "load_settings",
    "normalize_ui_language",
    "save_settings",
]
