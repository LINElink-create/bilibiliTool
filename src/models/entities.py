from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class VideoItem:
    uid: str
    user_name: str
    bv: str
    url: str
    title: str
    play: Optional[str] = None
    duration: Optional[str] = None
    pub_date: Optional[str] = None
    collected_at: Optional[str] = None
    source: str = "bilibili"
    danmu: Optional[int] = None
    video_type: Optional[str] = None
    page_count: Optional[int] = None
    id: Optional[int] = None


@dataclass(slots=True)
class DownloadTask:
    video_id: int
    status: str = "pending"
    target_dir: Optional[str] = None
    format_selector: Optional[str] = None
    downloader: str = "yt-dlp"
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    id: Optional[int] = None


@dataclass(slots=True)
class MediaFile:
    video_id: int
    file_path: str
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    container: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    id: Optional[int] = None


@dataclass(slots=True)
class PlayHistory:
    media_file_id: int
    position_seconds: float
    play_count: int = 0
    completed: bool = False
    id: Optional[int] = None


@dataclass(slots=True)
class Setting:
    key: str
    value: str
    id: Optional[int] = None
