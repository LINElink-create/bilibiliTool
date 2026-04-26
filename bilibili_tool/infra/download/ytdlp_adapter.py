from __future__ import annotations

import shutil
import sys
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from bilibili_tool.domain import DownloadTask, VideoFormatOption, VideoFormatProbeResult


@dataclass(slots=True)
class DownloadExecutionResult:
    """保存一次下载执行后的主文件路径和补充说明。"""

    file_path: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class FfmpegStatus:
    """描述当前环境里 ffmpeg 和 ffprobe 是否可用。"""

    available: bool
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    location: str | None = None


@dataclass(slots=True)
class YtDlpAdapter:
    """把下载任务交给 yt-dlp 执行，并在可用时自动启用 ffmpeg 合并。"""

    user_agent: str
    executable: str = "yt-dlp"
    _ffmpeg_status: FfmpegStatus | None = field(default=None, init=False, repr=False)

    def build_command(self, task: DownloadTask) -> list[str]:
        """保留一份等价命令，便于调试当前下载参数。"""

        target_dir = task.target_dir or "."
        output_template = str(Path(target_dir) / "%(title)s [%(id)s].%(ext)s")
        command = [
            self.executable,
            task.source_url,
            "--no-playlist",
            "--user-agent",
            self.user_agent,
            "-o",
            output_template,
        ]
        if self._should_set_format(task.format_selector):
            command.extend(["-f", task.format_selector])

        ffmpeg_status = self.inspect_ffmpeg()
        if ffmpeg_status.available and ffmpeg_status.location is not None:
            command.extend(["--ffmpeg-location", ffmpeg_status.location])
        return command

    def inspect_ffmpeg(self) -> FfmpegStatus:
        """检查当前 Python 环境和系统 PATH 中是否存在 ffmpeg。"""

        if self._ffmpeg_status is not None:
            return self._ffmpeg_status

        ffmpeg_path = self._find_binary("ffmpeg")
        ffprobe_path = self._find_binary("ffprobe")
        location = str(Path(ffmpeg_path).parent) if ffmpeg_path else None
        self._ffmpeg_status = FfmpegStatus(
            available=bool(ffmpeg_path and ffprobe_path),
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            location=location,
        )
        return self._ffmpeg_status

    def probe_formats(
        self,
        source_url: str,
        *,
        cookie_file_path: Path | None = None,
    ) -> VideoFormatProbeResult:
        """读取一个视频当前可用的真实格式列表，不触发下载。"""

        from yt_dlp import YoutubeDL

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "http_headers": {
                "User-Agent": self.user_agent,
                "Referer": "https://www.bilibili.com/",
            },
        }
        ffmpeg_status = self.inspect_ffmpeg()
        if ffmpeg_status.available and ffmpeg_status.location is not None:
            options["ffmpeg_location"] = ffmpeg_status.location
        if cookie_file_path is not None:
            options["cookiefile"] = str(cookie_file_path)

        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(source_url, download=False)

        normalized_info = self._unwrap_playlist_entry(info)
        title = str(normalized_info.get("title") or source_url)
        # Only keep concrete format rows so the UI can render exactly what yt-dlp reports.
        formats = tuple(
            self._build_format_option(item)
            for item in normalized_info.get("formats") or []
            if isinstance(item, dict) and item.get("format_id")
        )
        return VideoFormatProbeResult(
            source_url=source_url,
            title=title,
            formats=formats,
        )

    def download(
        self,
        task: DownloadTask,
        *,
        cookie_file_path: Path | None = None,
        progress_hook: Callable[[dict[str, Any]], None] | None = None,
    ) -> DownloadExecutionResult:
        """执行一次真实下载，并按环境能力决定是否启用 ffmpeg 合并。"""

        ffmpeg_status = self.inspect_ffmpeg()
        if not ffmpeg_status.available and not self._should_set_format(task.format_selector):
            return self._download_separate_streams(
                task=task,
                cookie_file_path=cookie_file_path,
                progress_hook=progress_hook,
            )

        try:
            return self._download_with_selector(
                task=task,
                cookie_file_path=cookie_file_path,
                progress_hook=progress_hook,
                format_selector=task.format_selector,
            )
        except Exception as exc:
            error_text = str(exc)
            if self._should_set_format(task.format_selector):
                raise

            # auto 模式下，优先尝试一个更明确的音视频组合格式。
            if ffmpeg_status.available:
                try:
                    return self._download_with_selector(
                        task=task,
                        cookie_file_path=cookie_file_path,
                        progress_hook=progress_hook,
                        format_selector="bestvideo+bestaudio/best",
                    )
                except Exception:
                    raise exc

            # 没有 ffmpeg 时，auto 模式退化成分别下载视频轨和音频轨。
            if "ffmpeg is not installed" in error_text or "Requested format is not available" in error_text:
                return self._download_separate_streams(
                    task=task,
                    cookie_file_path=cookie_file_path,
                    progress_hook=progress_hook,
                )
            raise

    def build_options(
        self,
        *,
        task: DownloadTask,
        cookie_file_path: Path | None = None,
        progress_hook: Callable[[dict[str, Any]], None] | None = None,
        format_selector: str | None = None,
    ) -> dict[str, Any]:
        """构造 yt-dlp 选项，并在可用时显式接入 ffmpeg。"""

        target_dir = Path(task.target_dir or ".")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(target_dir / "%(title)s [%(id)s].%(ext)s")
        options: dict[str, Any] = {
            "outtmpl": output_template,
            "noplaylist": True,
            "nopart": False,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 1,
            "merge_output_format": "mp4",
            "http_headers": {
                "User-Agent": self.user_agent,
                "Referer": "https://www.bilibili.com/",
            },
        }

        resolved_selector = format_selector if format_selector is not None else task.format_selector
        if self._should_set_format(resolved_selector):
            options["format"] = resolved_selector

        ffmpeg_status = self.inspect_ffmpeg()
        if ffmpeg_status.available and ffmpeg_status.location is not None:
            options["ffmpeg_location"] = ffmpeg_status.location

        if cookie_file_path is not None:
            options["cookiefile"] = str(cookie_file_path)
        if progress_hook is not None:
            options["progress_hooks"] = [progress_hook]
        return options

    def _download_with_selector(
        self,
        *,
        task: DownloadTask,
        cookie_file_path: Path | None,
        progress_hook: Callable[[dict[str, Any]], None] | None,
        format_selector: str | None,
    ) -> DownloadExecutionResult:
        """按指定 selector 执行一次标准下载。"""

        from yt_dlp import YoutubeDL

        options = self.build_options(
            task=task,
            cookie_file_path=cookie_file_path,
            progress_hook=progress_hook,
            format_selector=format_selector,
        )
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(task.source_url, download=True)
            return DownloadExecutionResult(file_path=self._resolve_output_path(info, downloader))

    def _download_separate_streams(
        self,
        *,
        task: DownloadTask,
        cookie_file_path: Path | None,
        progress_hook: Callable[[dict[str, Any]], None] | None,
    ) -> DownloadExecutionResult:
        """在没有 ffmpeg 时分别下载视频轨和音频轨，避免整单失败。"""

        video_path = self._download_stream(
            task=task,
            cookie_file_path=cookie_file_path,
            progress_hook=progress_hook,
            format_selector="bestvideo[vcodec!=none]",
            output_template=self._build_tagged_output_template(task, "video"),
        )
        audio_path = self._download_stream(
            task=task,
            cookie_file_path=cookie_file_path,
            progress_hook=None,
            format_selector="bestaudio[acodec!=none]",
            output_template=self._build_tagged_output_template(task, "audio"),
        )
        note = f"ffmpeg not found, downloaded separate streams. audio={audio_path}"
        return DownloadExecutionResult(file_path=video_path, note=note)

    def _download_stream(
        self,
        *,
        task: DownloadTask,
        cookie_file_path: Path | None,
        progress_hook: Callable[[dict[str, Any]], None] | None,
        format_selector: str,
        output_template: str,
    ) -> str:
        """下载单独一路媒体流，作为无 ffmpeg 环境下的兜底方案。"""

        from yt_dlp import YoutubeDL

        options = self.build_options(
            task=task,
            cookie_file_path=cookie_file_path,
            progress_hook=progress_hook,
            format_selector=format_selector,
        )
        options["outtmpl"] = output_template
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(task.source_url, download=True)
            return self._resolve_output_path(info, downloader)

    def _resolve_output_path(self, info: dict[str, Any], downloader) -> str:
        """尽量从 yt-dlp 的返回值里拿到最终落盘文件路径。"""

        normalized_info = self._unwrap_playlist_entry(info)
        requested_downloads = normalized_info.get("requested_downloads") or []
        for item in requested_downloads:
            if not isinstance(item, dict):
                continue
            file_path = item.get("filepath") or item.get("_filename")
            if file_path:
                return str(file_path)

        direct_path = normalized_info.get("filepath") or normalized_info.get("_filename")
        if direct_path:
            return str(direct_path)

        return str(downloader.prepare_filename(normalized_info))

    @staticmethod
    def _unwrap_playlist_entry(info: dict[str, Any]) -> dict[str, Any]:
        """单视频模式下仍可能拿到 entries，统一回落到第一项。"""

        if info.get("entries"):
            entries = info["entries"]
            first_entry = next((entry for entry in entries if entry), None)
            if isinstance(first_entry, dict):
                return first_entry
        return info

    @staticmethod
    def _should_set_format(format_selector: str | None) -> bool:
        """默认格式交给 yt-dlp 自选，只有显式指定时才写入 format。"""

        normalized = (format_selector or "").strip().lower()
        return normalized not in {"", "auto", "default"}

    @staticmethod
    def _build_tagged_output_template(task: DownloadTask, tag: str) -> str:
        """为分离流下载生成带标签的输出模板。"""

        target_dir = Path(task.target_dir or ".")
        target_dir.mkdir(parents=True, exist_ok=True)
        return str(target_dir / f"%(title)s [%(id)s] [{tag}].%(ext)s")

    @staticmethod
    def _candidate_binary_paths(binary_name: str) -> list[Path]:
        """覆盖 PATH、当前 conda 环境和常见 ffmpeg 目录。"""

        executable_name = f"{binary_name}.exe" if sys.platform.startswith("win") else binary_name
        candidates: list[Path] = []

        binary_path = shutil.which(binary_name)
        if binary_path:
            candidates.append(Path(binary_path))

        prefixes: list[Path] = []

        def add_prefix(value: str | Path | None) -> None:
            if not value:
                return
            prefix = Path(value)
            if prefix not in prefixes:
                prefixes.append(prefix)

        add_prefix(os.environ.get("CONDA_PREFIX"))
        add_prefix(sys.prefix)
        if getattr(sys, "frozen", False):
            add_prefix(Path(sys.executable).resolve().parent)
        bundle_dir = getattr(sys, "_MEIPASS", None)
        add_prefix(bundle_dir)

        home = Path.home()
        for root in (Path(sys.prefix), home / "anaconda3", home / "miniconda3"):
            add_prefix(root)
            add_prefix(root / "envs" / "bilibiliTool")

        seen: set[Path] = set()
        for prefix in prefixes:
            for candidate in (
                prefix / executable_name,
                prefix / "Scripts" / executable_name,
                prefix / "Library" / "bin" / executable_name,
                prefix / "bin" / executable_name,
                prefix / "ffmpeg" / executable_name,
            ):
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)
        return candidates

    @staticmethod
    def _build_format_option(item: dict[str, Any]) -> VideoFormatOption:
        """把 yt-dlp 原始格式字典收敛成 GUI 更容易展示的字段。"""

        width = item.get("width")
        height = item.get("height")
        resolution = item.get("resolution")
        if not resolution and width and height:
            resolution = f"{width}x{height}"

        filesize = item.get("filesize") or item.get("filesize_approx")
        filesize_text = YtDlpAdapter._format_filesize(filesize)
        note_parts = [
            str(item.get("format_note") or "").strip(),
            str(item.get("dynamic_range") or "").strip(),
        ]
        note = " | ".join(part for part in note_parts if part) or None
        return VideoFormatOption(
            format_id=str(item.get("format_id")),
            ext=item.get("ext"),
            resolution=resolution,
            vcodec=item.get("vcodec"),
            acodec=item.get("acodec"),
            protocol=item.get("protocol"),
            filesize_text=filesize_text,
            note=note,
        )

    @staticmethod
    def _format_filesize(value: Any) -> str | None:
        """把字节大小压缩成更易读的文本。"""

        if not isinstance(value, (int, float)) or value <= 0:
            return None
        units = ["B", "KiB", "MiB", "GiB"]
        size = float(value)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f}{units[unit_index]}"

    def _find_binary(self, binary_name: str) -> str | None:
        """返回当前环境中第一个存在的二进制路径。"""

        for candidate in self._candidate_binary_paths(binary_name):
            if candidate.exists():
                return str(candidate)
        return None
