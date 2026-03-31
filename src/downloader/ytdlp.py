from __future__ import annotations

import subprocess
from pathlib import Path


class YtDlpDownloader:
    def __init__(self, executable: str = "yt-dlp", format_selector: str = "bestvideo+bestaudio/best") -> None:
        self.executable = executable
        self.format_selector = format_selector

    def build_command(self, url: str, output_dir: Path) -> list[str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(output_dir / "%(uploader)s" / "%(title)s [%(id)s].%(ext)s")
        return [
            self.executable,
            "--newline",
            "--write-info-json",
            "--write-thumbnail",
            "--format",
            self.format_selector,
            "--output",
            output_template,
            url,
        ]

    def download(self, url: str, output_dir: Path) -> subprocess.CompletedProcess[str]:
        command = self.build_command(url, output_dir)
        return subprocess.run(command, check=False, text=True, capture_output=True)
