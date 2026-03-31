from __future__ import annotations

import subprocess
from pathlib import Path


class MPVPlayer:
    def __init__(self, executable: str = "mpv", ipc_name: str = "bilibiliTool-mpv") -> None:
        self.executable = executable
        self.ipc_name = ipc_name

    def build_command(self, media_path: Path) -> list[str]:
        return [
            self.executable,
            "--force-window=yes",
            "--save-position-on-quit",
            f"--input-ipc-server=\\\\.\\pipe\\{self.ipc_name}",
            str(media_path),
        ]

    def play(self, media_path: Path) -> subprocess.Popen[str]:
        command = self.build_command(media_path)
        return subprocess.Popen(command, text=True)
