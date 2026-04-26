from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from bilibili_tool.config import AppSettings
from bilibili_tool.domain import (
    ApiCallPreview,
    FavoriteFetchResult,
    FavoriteProbeResult,
    QrLoginDraft,
    QrLoginInitResult,
    QrLoginPollResult,
    VideoRecord,
)


@dataclass(slots=True)
class BilibiliClient:
    """封装 B 站请求，保持低频、单次、可控。"""

    settings: AppSettings
    cookies: dict[str, str] = field(default_factory=dict)

    def set_cookies(self, cookies: dict[str, str]) -> None:
        """更新后续请求要携带的 Cookie。"""

        self.cookies = {key: value for key, value in cookies.items() if value}

    def build_session(self) -> httpx.Client:
        """创建带默认请求头和 Cookie 的同步客户端。"""

        headers = {
            "User-Agent": self.settings.user_agent,
            "Referer": "https://www.bilibili.com/",
        }
        return httpx.Client(
            headers=headers,
            cookies=self.cookies,
            timeout=self.settings.request_timeout_seconds,
        )

    def _request_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """发起一次受控 GET 请求并返回 JSON 结果。"""

        with self.build_session() as session:
            response = session.get(url, params=params)

        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} from {url}")

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Non-JSON response from {url}") from exc

    def build_qr_login_draft(self) -> QrLoginDraft:
        """生成二维码登录流程的本地预演说明，不发起真实网络请求。"""

        steps = (
            ApiCallPreview(
                name="申请二维码",
                method="GET",
                url="https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                purpose="向 B 站申请一次新的二维码和轮询 key。",
            ),
            ApiCallPreview(
                name="查询扫码状态",
                method="GET",
                url="https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                purpose="单次查询二维码是否已被扫码、确认或过期。",
            ),
            ApiCallPreview(
                name="保存登录会话",
                method="LOCAL",
                url="data/bilibili_tool.db::auth_sessions",
                purpose="把 SESSDATA、bili_jct 和用户信息保存到本地数据库。",
            ),
        )
        return QrLoginDraft(
            title="二维码登录流程预览",
            summary="当前界面默认只在你点击按钮时发起单次请求，避免高频访问。",
            steps=steps,
        )

    def init_qr_login(self) -> QrLoginInitResult:
        """真实请求一次二维码初始化接口。"""

        payload = self._request_json("https://passport.bilibili.com/x/passport-login/web/qrcode/generate")
        code = int(payload.get("code", -1))
        data = payload.get("data") or {}
        if code != 0:
            return QrLoginInitResult(
                success=False,
                message=f"二维码初始化失败：code={code} message={payload.get('message')}",
                qrcode_url=None,
                qrcode_key=None,
            )
        return QrLoginInitResult(
            success=True,
            message="二维码初始化成功，可以把 URL 转成图片展示给用户。",
            qrcode_url=data.get("url"),
            qrcode_key=data.get("qrcode_key"),
        )

    def poll_qr_login(self, qrcode_key: str) -> QrLoginPollResult:
        """查询一次二维码当前状态，不做自动轮询。"""

        payload = self._request_json(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
            params={"qrcode_key": qrcode_key},
        )
        code = int(payload.get("code", -1))
        data = payload.get("data") or {}
        if code != 0:
            return QrLoginPollResult(
                success=False,
                status_code=code,
                message=f"二维码状态查询失败：code={code} message={payload.get('message')}",
                redirect_url=None,
                refresh_token=None,
            )

        status_code = int(data.get("code", -1))
        status_text = {
            86101: "等待扫码",
            86090: "已扫码，等待手机端确认",
            86038: "二维码已过期，请重新申请",
            0: "登录已确认，可以进入后续会话落库流程",
        }.get(status_code, f"未知状态码 {status_code}")
        return QrLoginPollResult(
            success=status_code == 0,
            status_code=status_code,
            message=status_text,
            redirect_url=data.get("url"),
            refresh_token=data.get("refresh_token"),
        )

    def build_user_video_preview(self, uid: str) -> ApiCallPreview:
        """预览通过空间投稿网页同步时会访问的页面。"""

        return ApiCallPreview(
            name="按 UID 打开投稿网页",
            method="GET",
            url=f"https://space.bilibili.com/{uid}/video?tid=0&pn=1&keyword=&order=pubdate",
            purpose="模拟浏览器打开 UP 主空间投稿页，渲染后从网页内容中提取 BV、标题和卡片信息。",
        )

    def build_favorite_preview(self, favorite_id: str) -> ApiCallPreview:
        """预览读取收藏夹内容时会调用的接口。"""

        return ApiCallPreview(
            name="按收藏夹拉取内容",
            method="GET",
            url=f"https://api.bilibili.com/x/v3/fav/resource/list?media_id={favorite_id}",
            purpose="读取收藏夹分页内容，后续转成视频元数据和下载任务。",
        )

    def validate_favorite(self, favorite_id: str) -> FavoriteProbeResult:
        """真实请求一次收藏夹接口，确认它是否可访问。"""

        try:
            payload = self._request_json(
                "https://api.bilibili.com/x/v3/fav/resource/list",
                params={"media_id": favorite_id, "pn": 1, "ps": 1, "platform": "web"},
            )
        except RuntimeError as exc:
            return FavoriteProbeResult(
                success=False,
                favorite_id=favorite_id,
                title=None,
                owner_name=None,
                media_count=None,
                message=f"收藏夹校验失败：{exc}",
            )

        code = int(payload.get("code", -1))
        data = payload.get("data") or {}
        info = data.get("info") or {}
        if code != 0:
            return FavoriteProbeResult(
                success=False,
                favorite_id=favorite_id,
                title=None,
                owner_name=None,
                media_count=None,
                message=f"收藏夹校验失败：code={code} message={payload.get('message')}",
            )

        upper = info.get("upper") or {}
        return FavoriteProbeResult(
            success=True,
            favorite_id=favorite_id,
            title=info.get("title"),
            owner_name=upper.get("name"),
            media_count=info.get("media_count"),
            message="收藏夹接口可访问，可以继续做单页同步。",
        )

    def fetch_favorite_page(self, favorite_id: str, *, page: int = 1, page_size: int = 20) -> FavoriteFetchResult:
        """抓取收藏夹单页内容，并转换成可直接落库的视频记录。"""

        try:
            payload = self._request_json(
                "https://api.bilibili.com/x/v3/fav/resource/list",
                params={"media_id": favorite_id, "pn": page, "ps": page_size, "platform": "web"},
            )
        except RuntimeError as exc:
            return FavoriteFetchResult(
                success=False,
                favorite_id=favorite_id,
                title=None,
                owner_name=None,
                message=f"收藏夹同步失败：{exc}",
                videos=(),
            )

        code = int(payload.get("code", -1))
        data = payload.get("data") or {}
        info = data.get("info") or {}
        if code != 0:
            return FavoriteFetchResult(
                success=False,
                favorite_id=favorite_id,
                title=None,
                owner_name=None,
                message=f"收藏夹同步失败：code={code} message={payload.get('message')}",
                videos=(),
            )

        upper = info.get("upper") or {}
        medias = data.get("medias") or []
        if not medias:
            return FavoriteFetchResult(
                success=False,
                favorite_id=favorite_id,
                title=info.get("title"),
                owner_name=upper.get("name"),
                message="收藏夹接口返回了空视频列表，可能需要登录后才能读取具体内容。",
                videos=(),
            )

        videos: list[VideoRecord] = []
        for media in medias:
            bvid = media.get("bvid")
            if not bvid:
                continue
            owner = media.get("upper") or {}
            pub_ts = media.get("pubtime")
            videos.append(
                VideoRecord(
                    bvid=bvid,
                    aid=media.get("id"),
                    title=media.get("title") or bvid,
                    page_count=int(media.get("page") or 1),
                    owner_uid=str(owner.get("mid")) if owner.get("mid") else None,
                    owner_name=owner.get("name"),
                    cover_url=media.get("cover"),
                    description=media.get("intro"),
                    duration_seconds=int(media.get("duration") or 0) or None,
                    pub_time=datetime.fromtimestamp(pub_ts) if pub_ts else None,
                    source_url=f"https://www.bilibili.com/video/{bvid}",
                )
            )

        return FavoriteFetchResult(
            success=True,
            favorite_id=favorite_id,
            title=info.get("title"),
            owner_name=upper.get("name"),
            message=f"收藏夹第 {page} 页已抓取，返回 {len(videos)} 条视频。",
            videos=tuple(videos),
        )
