from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """定义应用当前支持的来源类型。"""

    USER = "user"
    FAVORITE = "favorite"
    VIDEO = "video"


class SyncTaskStatus(StrEnum):
    """同步任务的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class DownloadStatus(StrEnum):
    """下载任务的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"

