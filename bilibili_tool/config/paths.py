from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """集中管理桌面应用的工作目录，避免路径散落在业务代码里。"""

    root: Path
    data_dir: Path
    logs_dir: Path
    exports_dir: Path
    downloads_dir: Path
    browser_profile_dir: Path
    database_path: Path
    settings_path: Path


def build_app_paths(root: Path | None = None) -> AppPaths:
    """基于项目根目录构建运行期路径，并和旧项目数据隔离。"""

    project_root = root or Path.cwd()
    data_dir = project_root / "data"
    logs_dir = project_root / "logs"
    exports_dir = project_root / "exports"
    downloads_dir = project_root / "downloads"
    browser_profile_dir = data_dir / "browser_profile"
    database_path = data_dir / "bilibili_tool.db"
    settings_path = data_dir / "settings.json"
    return AppPaths(
        root=project_root,
        data_dir=data_dir,
        logs_dir=logs_dir,
        exports_dir=exports_dir,
        downloads_dir=downloads_dir,
        browser_profile_dir=browser_profile_dir,
        database_path=database_path,
        settings_path=settings_path,
    )
