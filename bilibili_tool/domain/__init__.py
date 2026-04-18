"""Domain models for bilibiliTool."""

from bilibili_tool.domain.entities import AuthSession, DownloadTask, SourceRecord, SyncTask, VideoRecord
from bilibili_tool.domain.enums import DownloadStatus, SourceKind, SyncTaskStatus
from bilibili_tool.domain.value_objects import (
    ApiCallPreview,
    BrowserSessionSnapshot,
    DashboardSummary,
    FavoriteFetchResult,
    FavoriteProbeResult,
    FavoriteSyncResult,
    LoginState,
    QrLoginDraft,
    QrLoginInitResult,
    QrLoginPollResult,
    SourcePreview,
    UserProbeCandidate,
    UserProbeResult,
    VideoFormatOption,
    VideoFormatProbeResult,
)

__all__ = [
    "ApiCallPreview",
    "AuthSession",
    "BrowserSessionSnapshot",
    "DashboardSummary",
    "DownloadStatus",
    "DownloadTask",
    "FavoriteFetchResult",
    "FavoriteProbeResult",
    "FavoriteSyncResult",
    "LoginState",
    "QrLoginDraft",
    "QrLoginInitResult",
    "QrLoginPollResult",
    "SourceKind",
    "SourcePreview",
    "SourceRecord",
    "SyncTask",
    "SyncTaskStatus",
    "UserProbeCandidate",
    "UserProbeResult",
    "VideoFormatOption",
    "VideoFormatProbeResult",
    "VideoRecord",
]
