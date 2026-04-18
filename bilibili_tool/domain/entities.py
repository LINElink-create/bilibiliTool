from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bilibili_tool.domain.enums import DownloadStatus, SourceKind, SyncTaskStatus


@dataclass(slots=True)
class SourceRecord:
    """描述一个待同步的来源，例如 UP 主主页、收藏夹或单视频。"""

    kind: SourceKind
    source_key: str
    display_name: str
    url: str
    is_enabled: bool = True
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_sync_at: datetime | None = None


@dataclass(slots=True)
class VideoRecord:
    """保存视频元数据，供资源库展示和下载队列复用。"""

    bvid: str
    title: str
    page_count: int = 1
    owner_uid: str | None = None
    owner_name: str | None = None
    cover_url: str | None = None
    description: str | None = None
    duration_seconds: int | None = None
    pub_time: datetime | None = None
    source_url: str | None = None
    aid: int | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SyncTask:
    """记录一次来源同步任务，后续同步 worker 会持续更新它。"""

    source_id: int
    status: SyncTaskStatus = SyncTaskStatus.PENDING
    stage: str = 'queued'
    message: str | None = None
    id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    items_total: int = 0
    items_new: int = 0
    items_updated: int = 0


@dataclass(slots=True)
class DownloadTask:
    """记录一个待执行的下载请求，实际执行由下载 worker 接管。"""

    source_url: str
    display_name: str
    format_selector: str = 'bestvideo+bestaudio/best'
    target_dir: str | None = None
    status: DownloadStatus = DownloadStatus.PENDING
    video_id: int | None = None
    file_path: str | None = None
    progress: float = 0.0
    error_message: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class AuthSession:
    """保存 B 站登录态，后续 HTTP 请求和下载器都会依赖它。"""

    session_name: str
    cookie_json: str
    csrf: str | None = None
    is_active: bool = True
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None