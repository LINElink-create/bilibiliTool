from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    export_dir: Path
    database_path: Path
    downloads_dir: Path


def build_app_paths(root: Path | None = None) -> AppPaths:
    project_root = root or Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    export_dir = data_dir / "exports"
    downloads_dir = data_dir / "downloads"
    database_path = data_dir / "app.db"
    return AppPaths(
        root=project_root,
        data_dir=data_dir,
        export_dir=export_dir,
        database_path=database_path,
        downloads_dir=downloads_dir,
    )
