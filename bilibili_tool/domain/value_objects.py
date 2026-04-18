from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.domain.entities import VideoRecord
from bilibili_tool.domain.enums import SourceKind


@dataclass(frozen=True, slots=True)
class LoginState:
    """描述登录中心当前需要展示的登录状态。"""

    is_logged_in: bool
    session_name: str
    display_message: str


@dataclass(frozen=True, slots=True)
class BrowserSessionSnapshot:
    """描述浏览器里当前捕获到的登录 Cookie 状态。"""

    cookie_count: int
    has_sessdata: bool
    has_csrf: bool
    has_user_id: bool
    is_ready: bool
    missing_cookie_names: tuple[str, ...]
    cookie_json: str


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """聚合首页需要展示的本地统计信息。"""

    source_count: int
    video_count: int
    download_count: int
    active_session_name: str


@dataclass(frozen=True, slots=True)
class SourcePreview:
    """保存来源输入的本地解析结果，供 CLI 和 GUI 预览。"""

    kind: SourceKind
    input_mode: str
    input_value: str
    display_name: str
    resolved_key: str | None
    canonical_url: str | None
    is_ready_for_save: bool
    message: str


@dataclass(frozen=True, slots=True)
class ApiCallPreview:
    """描述未来会发起的一次 API 请求，当前仅用于预览。"""

    name: str
    method: str
    url: str
    purpose: str


@dataclass(frozen=True, slots=True)
class QrLoginDraft:
    """描述二维码登录流程的本地预演结果。"""

    title: str
    summary: str
    steps: tuple[ApiCallPreview, ...]


@dataclass(frozen=True, slots=True)
class QrLoginInitResult:
    """保存一次二维码初始化请求的结果。"""

    success: bool
    message: str
    qrcode_url: str | None
    qrcode_key: str | None


@dataclass(frozen=True, slots=True)
class QrLoginPollResult:
    """保存一次二维码状态查询的结果。"""

    success: bool
    status_code: int | None
    message: str
    redirect_url: str | None
    refresh_token: str | None


@dataclass(frozen=True, slots=True)
class UserProbeCandidate:
    """描述一个由用户名搜索返回的候选用户。"""

    uid: str
    name: str
    homepage_url: str
    fans: int | None = None
    sign: str | None = None


@dataclass(frozen=True, slots=True)
class UserProbeResult:
    """描述一次用户名或 UID 探测的结果。"""

    success: bool
    input_mode: str
    input_value: str
    message: str
    items: tuple[str, ...]
    candidates: tuple[UserProbeCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class FavoriteProbeResult:
    """描述一次收藏夹校验请求的结果。"""

    success: bool
    favorite_id: str
    title: str | None
    owner_name: str | None
    media_count: int | None
    message: str


@dataclass(frozen=True, slots=True)
class FavoriteFetchResult:
    """保存收藏夹第一页抓取结果，供同步服务写入本地库。"""

    success: bool
    favorite_id: str
    title: str | None
    owner_name: str | None
    message: str
    videos: tuple[VideoRecord, ...]


@dataclass(frozen=True, slots=True)
class FavoriteSyncResult:
    """描述一次收藏夹单页同步的最终结果。"""

    success: bool
    source_id: int
    source_name: str
    message: str
    synced_count: int
    new_count: int
    updated_count: int


@dataclass(frozen=True, slots=True)
class VideoFormatOption:
    """描述一个视频当前可用的下载格式。"""

    format_id: str
    ext: str | None
    resolution: str | None
    vcodec: str | None
    acodec: str | None
    protocol: str | None
    filesize_text: str | None
    note: str | None


@dataclass(frozen=True, slots=True)
class VideoFormatProbeResult:
    """保存一次视频格式探测的标题和格式列表。"""

    source_url: str
    title: str
    formats: tuple[VideoFormatOption, ...]
