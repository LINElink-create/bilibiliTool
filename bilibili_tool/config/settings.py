from __future__ import annotations

import json
import locale
from dataclasses import dataclass, replace
from pathlib import Path

from bilibili_tool.config.paths import AppPaths

SUPPORTED_UI_LANGUAGES = ("zh-CN", "en-US")


@dataclass(frozen=True, slots=True)
class AppSettings:
    """保存当前阶段需要的基础运行配置。"""

    request_timeout_seconds: int = 20
    sync_concurrency: int = 2
    download_concurrency: int = 2
    ui_language: str = "zh-CN"
    show_login_intro_dialog: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )


def normalize_ui_language(value: str | None) -> str:
    """把外部传入的语言值归一化到受支持的语言列表。"""

    if not value:
        return "zh-CN"

    lowered = value.lower()
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en-US"
    return "zh-CN"


def detect_system_language() -> str:
    """在没有本地配置时，根据系统区域信息推断默认语言。"""

    candidates = [
        locale.getlocale()[0],
        locale.getdefaultlocale()[0] if hasattr(locale, "getdefaultlocale") else None,
    ]
    for candidate in candidates:
        normalized = normalize_ui_language(candidate)
        if normalized in SUPPORTED_UI_LANGUAGES:
            return normalized
    return "zh-CN"


def _resolve_settings_path(path_or_paths: Path | AppPaths | None) -> Path | None:
    """统一解析配置文件路径。"""

    if path_or_paths is None:
        return None
    if isinstance(path_or_paths, AppPaths):
        return path_or_paths.settings_path
    return path_or_paths


def load_settings(path_or_paths: Path | AppPaths | None = None) -> AppSettings:
    """优先读取本地配置文件，没有则回退到系统语言。"""

    settings_path = _resolve_settings_path(path_or_paths)
    default_settings = AppSettings(ui_language=detect_system_language())

    if settings_path is None or not settings_path.exists():
        return default_settings

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default_settings

    return AppSettings(
        request_timeout_seconds=int(data.get("request_timeout_seconds", default_settings.request_timeout_seconds)),
        sync_concurrency=int(data.get("sync_concurrency", default_settings.sync_concurrency)),
        download_concurrency=int(data.get("download_concurrency", default_settings.download_concurrency)),
        ui_language=normalize_ui_language(data.get("ui_language")),
        show_login_intro_dialog=bool(data.get("show_login_intro_dialog", default_settings.show_login_intro_dialog)),
        user_agent=str(data.get("user_agent", default_settings.user_agent)),
    )


def save_settings(paths: AppPaths, settings: AppSettings) -> AppSettings:
    """把设置写入本地文件，并返回归一化后的设置对象。"""

    normalized = replace(settings, ui_language=normalize_ui_language(settings.ui_language))
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_timeout_seconds": normalized.request_timeout_seconds,
        "sync_concurrency": normalized.sync_concurrency,
        "download_concurrency": normalized.download_concurrency,
        "ui_language": normalized.ui_language,
        "show_login_intro_dialog": normalized.show_login_intro_dialog,
        "user_agent": normalized.user_agent,
    }
    paths.settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized
