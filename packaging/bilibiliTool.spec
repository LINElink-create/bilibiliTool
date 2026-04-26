# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_submodules


spec_dir = Path(SPECPATH).resolve()
project_root = spec_dir.parent
entry_script = project_root / "bilibili_tool" / "app" / "desktop_entry.py"


def find_binary(name: str) -> str | None:
    executable = f"{name}.exe" if sys.platform.startswith("win") else name
    prefixes = [
        os.environ.get("CONDA_PREFIX"),
        sys.prefix,
        Path.home() / "anaconda3" / "envs" / "bilibiliTool",
        Path.home() / "miniconda3" / "envs" / "bilibiliTool",
    ]
    for raw_prefix in prefixes:
        if not raw_prefix:
            continue
        prefix = Path(raw_prefix)
        for candidate in (
            prefix / executable,
            prefix / "Scripts" / executable,
            prefix / "Library" / "bin" / executable,
            prefix / "bin" / executable,
        ):
            if candidate.exists():
                return str(candidate)
    return None


binaries = []
for binary_name in ("ffmpeg", "ffprobe"):
    binary_path = find_binary(binary_name)
    if binary_path:
        binaries.append((binary_path, "ffmpeg"))

hiddenimports = collect_submodules("yt_dlp") + [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtPositioning",
]

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bilibiliTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="bilibiliTool",
)
