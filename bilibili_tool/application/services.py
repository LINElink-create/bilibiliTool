from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from bilibili_tool.config import (
    AppPaths,
    AppSettings,
    build_app_paths,
    load_settings,
    normalize_ui_language,
    save_settings,
)
from bilibili_tool.domain import (
    AuthSession,
    BrowserSessionSnapshot,
    DashboardSummary,
    DownloadQueueResult,
    DownloadStatus,
    DownloadTask,
    FavoriteProbeResult,
    FavoriteSyncResult,
    LoginState,
    QrLoginDraft,
    QrLoginInitResult,
    QrLoginPollResult,
    SourceKind,
    SourcePreview,
    SourceRecord,
    SourceSyncResult,
    SyncTask,
    SyncTaskStatus,
    UserProbeResult,
    VideoFormatProbeResult,
    VideoRecord,
)
from bilibili_tool.infra.download import YtDlpAdapter
from bilibili_tool.infra.bilibili import BilibiliClient
from bilibili_tool.infra.browser import BrowserUserArchiveScraper, BrowserUserSearch
from bilibili_tool.infra.db import (
    AuthSessionRepository,
    Database,
    DownloadTaskRepository,
    SourceRepository,
    SyncTaskRepository,
    VideoRepository,
)
from bilibili_tool.infra.logging import configure_logging


@dataclass(frozen=True, slots=True)
class SourceDraft:
    """描述已经解析完成并可直接落库的来源。"""

    kind: SourceKind
    source_key: str
    display_name: str
    url: str


class SourceInputParser:
    """把 UID、用户名、BV 号和收藏夹链接统一解析成预览结果。"""

    USER_PATTERN = re.compile(r"space\.bilibili\.com/(?P<uid>\d+)")
    FAVORITE_PATTERN = re.compile(r"(fid=|/list/ml)(?P<fid>\d+)")
    VIDEO_PATTERN = re.compile(r"(?P<bvid>BV[0-9A-Za-z]{10})")

    def preview(self, kind: SourceKind, raw_value: str, display_name: str | None = None) -> SourcePreview:
        """根据输入内容生成本地解析预览，而不发起任何网络请求。"""

        value = raw_value.strip()
        if not value:
            raise ValueError("Source value cannot be empty.")

        if kind is SourceKind.USER:
            return self._preview_user(value=value, display_name=display_name)
        if kind is SourceKind.FAVORITE:
            return self._preview_favorite(value=value, display_name=display_name)
        return self._preview_video(value=value, display_name=display_name)

    def parse(self, kind: SourceKind, raw_value: str, display_name: str | None = None) -> SourceDraft:
        """把可落库的来源预览转换成正式来源对象。"""

        preview = self.preview(kind=kind, raw_value=raw_value, display_name=display_name)
        if not preview.is_ready_for_save or preview.resolved_key is None or preview.canonical_url is None:
            raise ValueError(preview.message)
        return SourceDraft(
            kind=preview.kind,
            source_key=preview.resolved_key,
            display_name=preview.display_name,
            url=preview.canonical_url,
        )

    def _preview_user(self, value: str, display_name: str | None) -> SourcePreview:
        """支持按 UID、用户主页链接或用户名生成用户来源预览。"""

        if value.isdigit():
            uid = value
            return SourcePreview(
                kind=SourceKind.USER,
                input_mode="uid",
                input_value=value,
                display_name=display_name or f"UP 主 {uid}",
                resolved_key=uid,
                canonical_url=f"https://space.bilibili.com/{uid}",
                is_ready_for_save=True,
                message="已识别为 UID，可直接保存为来源。",
            )

        matched = self.USER_PATTERN.search(value)
        if matched:
            uid = matched.group("uid")
            return SourcePreview(
                kind=SourceKind.USER,
                input_mode="user_url",
                input_value=value,
                display_name=display_name or f"UP 主 {uid}",
                resolved_key=uid,
                canonical_url=f"https://space.bilibili.com/{uid}",
                is_ready_for_save=True,
                message="已从用户主页链接中提取 UID，可直接保存。",
            )

        return SourcePreview(
            kind=SourceKind.USER,
            input_mode="user_name",
            input_value=value,
            display_name=display_name or value,
            resolved_key=None,
            canonical_url=None,
            is_ready_for_save=False,
            message="当前识别为用户名。后续需要通过浏览器搜索页先解析成 UID 再保存。",
        )

    def _preview_favorite(self, value: str, display_name: str | None) -> SourcePreview:
        """支持按收藏夹 ID 或链接生成收藏夹来源预览。"""

        if value.isdigit():
            favorite_id = value
            return SourcePreview(
                kind=SourceKind.FAVORITE,
                input_mode="favorite_id",
                input_value=value,
                display_name=display_name or f"收藏夹 {favorite_id}",
                resolved_key=favorite_id,
                canonical_url=f"https://www.bilibili.com/list/ml{favorite_id}",
                is_ready_for_save=True,
                message="已识别为收藏夹 ID，可直接保存。",
            )

        matched = self.FAVORITE_PATTERN.search(value)
        if matched:
            favorite_id = matched.group("fid")
            return SourcePreview(
                kind=SourceKind.FAVORITE,
                input_mode="favorite_url",
                input_value=value,
                display_name=display_name or f"收藏夹 {favorite_id}",
                resolved_key=favorite_id,
                canonical_url=f"https://www.bilibili.com/list/ml{favorite_id}",
                is_ready_for_save=True,
                message="已从收藏夹链接中提取 media_id，可直接保存。",
            )

        raise ValueError("Favorite source must be a favorite ID or a valid bilibili favorite URL.")

    def _preview_video(self, value: str, display_name: str | None) -> SourcePreview:
        """支持按 BV 号或视频链接生成单视频来源预览。"""

        matched = self.VIDEO_PATTERN.search(value)
        if not matched:
            raise ValueError("Video source must contain a valid BV id.")
        bvid = matched.group("bvid")
        input_mode = "video_url" if value != bvid else "bvid"
        return SourcePreview(
            kind=SourceKind.VIDEO,
            input_mode=input_mode,
            input_value=value,
            display_name=display_name or bvid,
            resolved_key=bvid,
            canonical_url=f"https://www.bilibili.com/video/{bvid}",
            is_ready_for_save=True,
            message="已识别为单视频来源，可直接保存。",
        )


class WorkspaceService:
    """负责初始化工作目录、数据库和本地日志。"""

    def __init__(self, paths: AppPaths, database: Database) -> None:
        self.paths = paths
        self.database = database

    def initialize(self) -> Path:
        """创建基础目录、数据库和日志文件。"""

        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.exports_dir.mkdir(parents=True, exist_ok=True)
        self.paths.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.paths.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        self.database.initialize()
        log_path = configure_logging(self.paths.logs_dir)
        logging.getLogger("bilibili_tool.workspace").info(
            "Workspace initialized. log=%s db=%s",
            log_path,
            self.paths.database_path,
        )
        return self.paths.database_path


class SourceService:
    """来源管理和单次同步服务。"""

    def __init__(
        self,
        parser: SourceInputParser,
        repository: SourceRepository,
        video_repository: VideoRepository,
        sync_task_repository: SyncTaskRepository,
        client: BilibiliClient,
        auth_session_repository: AuthSessionRepository,
        user_archive_scraper: BrowserUserArchiveScraper,
        browser_user_search: BrowserUserSearch,
    ) -> None:
        self.parser = parser
        self.repository = repository
        self.video_repository = video_repository
        self.sync_task_repository = sync_task_repository
        self.client = client
        self.auth_session_repository = auth_session_repository
        self.user_archive_scraper = user_archive_scraper
        self.browser_user_search = browser_user_search

    def preview_source(self, kind: SourceKind, raw_value: str, display_name: str | None = None) -> SourcePreview:
        """生成来源输入预览，供 GUI 和 CLI 做本地确认。"""

        return self.parser.preview(kind=kind, raw_value=raw_value, display_name=display_name)

    def add_source(self, kind: SourceKind, raw_value: str, display_name: str | None = None) -> int:
        """把用户输入标准化后写入来源表。"""

        draft = self.parser.parse(kind=kind, raw_value=raw_value, display_name=display_name)
        return self.repository.upsert(
            SourceRecord(
                kind=draft.kind,
                source_key=draft.source_key,
                display_name=draft.display_name,
                url=draft.url,
            )
        )

    def list_sources(self) -> list[SourceRecord]:
        """读取全部来源。"""

        return self.repository.list_all()

    def get_source_video_stats(self, source_id: int) -> tuple[int, int]:
        """读取来源关联视频总数和发布时间覆盖数量，供管理台展示。"""

        return self.video_repository.count_by_source(source_id)

    def rename_source(self, source_id: int, display_name: str) -> SourceRecord:
        """重命名本地来源文件夹。"""

        cleaned_name = display_name.strip()
        if not cleaned_name:
            raise ValueError("Source name cannot be empty.")
        if self.repository.get_by_id(source_id) is None:
            raise ValueError(f"Source #{source_id} was not found.")
        self.repository.rename(source_id, cleaned_name)
        updated = self.repository.get_by_id(source_id)
        if updated is None:
            raise ValueError(f"Source #{source_id} could not be loaded after rename.")
        return updated

    def delete_source(self, source_id: int) -> None:
        """删除本地来源及其视频关联，不删除下载文件。"""

        if self.repository.get_by_id(source_id) is None:
            raise ValueError(f"Source #{source_id} was not found.")
        self.repository.delete(source_id)

    def describe_next_sync_step(self, preview: SourcePreview) -> str:
        """给来源预览补上未来实际同步时会调用的接口说明。"""

        if preview.kind is SourceKind.USER:
            if preview.resolved_key is None:
                return "下一阶段将通过嵌入浏览器访问 B 站搜索页，定位目标 UP 主并提取 UID。"
            return (
                f"下一阶段会模拟浏览器打开 https://space.bilibili.com/{preview.resolved_key}/video "
                "并从网页内容中提取该 UP 主的投稿列表。"
            )

        if preview.kind is SourceKind.FAVORITE and preview.resolved_key is not None:
            api_preview = self.client.build_favorite_preview(preview.resolved_key)
            return f"下一阶段将调用 {api_preview.name}：{api_preview.url}"

        return "下一阶段会把该视频加入同步或下载流程。"

    def probe_user_input(self, raw_value: str) -> UserProbeResult:
        """对用户输入做一次受控的真实探测。"""

        preview = self.preview_source(kind=SourceKind.USER, raw_value=raw_value)
        if preview.resolved_key is not None:
            return self.browser_user_search.inspect_user_homepage(preview.resolved_key)
        return self.browser_user_search.search_users(preview.input_value)

    def probe_favorite_input(self, raw_value: str) -> FavoriteProbeResult:
        """对收藏夹输入做一次受控的真实校验。"""

        self._refresh_client_cookies()
        preview = self.preview_source(kind=SourceKind.FAVORITE, raw_value=raw_value)
        if preview.resolved_key is None:
            raise ValueError(preview.message)
        return self.client.validate_favorite(preview.resolved_key)

    def sync_favorite_once(self, raw_value: str, display_name: str | None = None) -> FavoriteSyncResult:
        """把收藏夹第一页同步到本地资源库，避免高频抓取。"""

        self._refresh_client_cookies()
        preview = self.preview_source(kind=SourceKind.FAVORITE, raw_value=raw_value, display_name=display_name)
        if preview.resolved_key is None:
            raise ValueError(preview.message)

        source_id = self.add_source(kind=SourceKind.FAVORITE, raw_value=raw_value, display_name=display_name)
        source = self.repository.get_by_id(source_id)
        if source is None:
            raise ValueError("Saved source could not be loaded back from the database.")

        self.sync_task_repository.create(
            SyncTask(
                source_id=source_id,
                status=SyncTaskStatus.RUNNING,
                stage="favorite_page_1",
                message="Starting a single-page favorite sync.",
                started_at=datetime.now(),
            )
        )

        fetch_result = self.client.fetch_favorite_page(source.source_key, page=1, page_size=20)
        if not fetch_result.success:
            self.sync_task_repository.create(
                SyncTask(
                    source_id=source_id,
                    status=SyncTaskStatus.FAILED,
                    stage="favorite_page_1",
                    message=fetch_result.message,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                )
            )
            return FavoriteSyncResult(
                success=False,
                source_id=source_id,
                source_name=source.display_name,
                message=fetch_result.message,
                synced_count=0,
                new_count=0,
                updated_count=0,
            )

        new_count = 0
        updated_count = 0
        for video in fetch_result.videos:
            video_id, is_new = self.video_repository.upsert(video)
            self.video_repository.link_to_source(source_id, video_id)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        self.repository.mark_synced(source_id)
        summary_message = (
            f"收藏夹《{fetch_result.title or source.display_name}》已同步第一页，"
            f"共写入 {len(fetch_result.videos)} 条视频。"
        )
        self.sync_task_repository.create(
            SyncTask(
                source_id=source_id,
                status=SyncTaskStatus.SUCCESS,
                stage="favorite_page_1",
                message=summary_message,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                items_total=len(fetch_result.videos),
                items_new=new_count,
                items_updated=updated_count,
            )
        )
        return FavoriteSyncResult(
            success=True,
            source_id=source_id,
            source_name=source.display_name,
            message=summary_message,
            synced_count=len(fetch_result.videos),
            new_count=new_count,
            updated_count=updated_count,
        )

    def sync_favorite_all(
        self,
        raw_value: str,
        display_name: str | None = None,
        *,
        page_size: int = 20,
        max_pages: int = 20,
    ) -> SourceSyncResult:
        """分页同步整个收藏夹，默认设置上限以避免误触发超大抓取。"""

        self._refresh_client_cookies()
        preview = self.preview_source(kind=SourceKind.FAVORITE, raw_value=raw_value, display_name=display_name)
        if preview.resolved_key is None:
            raise ValueError(preview.message)

        source_id = self.add_source(kind=SourceKind.FAVORITE, raw_value=raw_value, display_name=display_name)
        source = self._require_source(source_id)
        return self._sync_paged_source(
            source=source,
            stage="favorite_full",
            page_size=page_size,
            max_pages=max_pages,
            fetch_page=lambda page: self.client.fetch_favorite_page(source.source_key, page=page, page_size=page_size),
            stop_on_short_page=True,
        )

    def sync_user_archive(
        self,
        raw_value: str,
        display_name: str | None = None,
        *,
        page_size: int = 60,
        max_pages: int = 20,
    ) -> SourceSyncResult:
        """分页同步 UP 主投稿历史。"""

        self._refresh_client_cookies()
        preview = self.preview_source(kind=SourceKind.USER, raw_value=raw_value, display_name=display_name)
        if preview.resolved_key is None:
            raise ValueError("请先通过 GUI 的用户名探测选择候选 UID，或直接传入 UID/用户主页链接。")

        source_id = self.add_source(kind=SourceKind.USER, raw_value=raw_value, display_name=display_name)
        source = self._require_source(source_id)
        return self._sync_paged_source(
            source=source,
            stage="user_archive",
            page_size=page_size,
            max_pages=max_pages,
            fetch_page=lambda page: self.user_archive_scraper.fetch_page(
                source.source_key,
                page=page,
                page_size=page_size,
            ),
            stop_on_short_page=False,
        )

    def _sync_paged_source(
        self,
        *,
        source: SourceRecord,
        stage: str,
        page_size: int,
        max_pages: int,
        fetch_page,
        stop_on_short_page: bool = True,
    ) -> SourceSyncResult:
        """执行分页来源同步，并把视频元数据写入资源库。"""

        if source.id is None:
            raise ValueError("Source must be saved before sync.")
        if page_size <= 0 or max_pages <= 0:
            raise ValueError("page_size and max_pages must be positive.")

        self.sync_task_repository.create(
            SyncTask(
                source_id=source.id,
                status=SyncTaskStatus.RUNNING,
                stage=stage,
                message=f"Starting {stage} sync.",
                started_at=datetime.now(),
            )
        )

        new_count = 0
        updated_count = 0
        synced_count = 0
        pages_done = 0
        last_message = ""
        seen_bvids: set[str] = set()

        for page in range(1, max_pages + 1):
            fetch_result = fetch_page(page)
            last_message = fetch_result.message
            if not fetch_result.success:
                if page == 1:
                    self.sync_task_repository.create(
                        SyncTask(
                            source_id=source.id,
                            status=SyncTaskStatus.FAILED,
                            stage=stage,
                            message=fetch_result.message,
                            started_at=datetime.now(),
                            finished_at=datetime.now(),
                            items_total=synced_count,
                            items_new=new_count,
                            items_updated=updated_count,
                        )
                    )
                    return SourceSyncResult(
                        success=False,
                        source_id=source.id,
                        source_name=source.display_name,
                        source_kind=source.kind,
                        message=fetch_result.message,
                        synced_count=synced_count,
                        new_count=new_count,
                        updated_count=updated_count,
                        page_count=pages_done,
                    )
                break

            if not fetch_result.videos:
                break

            fresh_videos = tuple(video for video in fetch_result.videos if video.bvid not in seen_bvids)
            if not fresh_videos:
                break

            pages_done += 1
            for video in fresh_videos:
                seen_bvids.add(video.bvid)
                video_id, is_new = self.video_repository.upsert(video)
                self.video_repository.link_to_source(source.id, video_id)
                synced_count += 1
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            if stop_on_short_page and len(fetch_result.videos) < page_size:
                break

        if pages_done:
            self.repository.mark_synced(source.id)
        summary_message = (
            f"{source.display_name} 同步完成：分页 {pages_done} 页，写入 {synced_count} 条视频，"
            f"新增 {new_count} 条，更新 {updated_count} 条。"
        )
        if not pages_done and last_message:
            summary_message = last_message
        self.sync_task_repository.create(
            SyncTask(
                source_id=source.id,
                status=SyncTaskStatus.SUCCESS if pages_done else SyncTaskStatus.FAILED,
                stage=stage,
                message=summary_message,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                items_total=synced_count,
                items_new=new_count,
                items_updated=updated_count,
            )
        )
        return SourceSyncResult(
            success=pages_done > 0,
            source_id=source.id,
            source_name=source.display_name,
            source_kind=source.kind,
            message=summary_message,
            synced_count=synced_count,
            new_count=new_count,
            updated_count=updated_count,
            page_count=pages_done,
        )

    def _require_source(self, source_id: int) -> SourceRecord:
        """读取刚保存的来源，不存在时给出明确错误。"""

        source = self.repository.get_by_id(source_id)
        if source is None:
            raise ValueError("Saved source could not be loaded back from the database.")
        return source

    def _refresh_client_cookies(self) -> None:
        """把本地活动登录态注入 API 客户端。"""

        session = self.auth_session_repository.get_active()
        if session is None:
            self.client.set_cookies({})
            self.user_archive_scraper.set_cookies({})
            return
        try:
            cookies = json.loads(session.cookie_json)
        except (TypeError, ValueError):
            self.client.set_cookies({})
            self.user_archive_scraper.set_cookies({})
            return
        if isinstance(cookies, dict):
            normalized_cookies = {str(key): str(value) for key, value in cookies.items()}
            self.client.set_cookies(normalized_cookies)
            self.user_archive_scraper.set_cookies(normalized_cookies)


class LibraryService:
    """资源库只读服务。"""

    def __init__(self, video_repository: VideoRepository) -> None:
        self.video_repository = video_repository

    def list_videos(self, limit: int = 100) -> list[VideoRecord]:
        """列出最近写入的视频。"""

        return self.video_repository.list_all(limit=limit)

    def list_source_videos(self, source_id: int, limit: int = 500) -> list[VideoRecord]:
        """列出某个来源已经同步到本地的视频。"""

        return self.video_repository.list_by_source(source_id=source_id, limit=limit)

    def unlink_video_from_source(self, source_id: int, video_id: int) -> None:
        """从当前来源文件夹移除视频，但保留视频元数据。"""

        self.video_repository.unlink_from_source(source_id=source_id, video_id=video_id)


class DownloadCancelledError(RuntimeError):
    """下载任务被用户主动取消时抛出的内部异常。"""


class DownloadService:
    """下载任务管理服务。"""

    DEFAULT_FORMAT_SELECTOR = "auto"

    def __init__(
        self,
        parser: SourceInputParser,
        repository: DownloadTaskRepository,
        auth_session_repository: AuthSessionRepository,
        video_repository: VideoRepository,
        source_repository: SourceRepository,
        paths: AppPaths,
        adapter: YtDlpAdapter,
    ) -> None:
        self.parser = parser
        self.repository = repository
        self.auth_session_repository = auth_session_repository
        self.video_repository = video_repository
        self.source_repository = source_repository
        self.paths = paths
        self.adapter = adapter
        self._progress_cache: dict[int, int] = {}
        self._cancel_requests: set[int] = set()

    def queue_url(
        self,
        url: str,
        display_name: str,
        format_selector: str | None = None,
        *,
        video_id: int | None = None,
        target_dir: str | Path | None = None,
    ) -> int:
        """先把下载请求写入下载表，为立即执行或后续重试做准备。"""

        resolved_target_dir = str(target_dir or self.paths.downloads_dir)
        return self.repository.create(
            DownloadTask(
                video_id=video_id,
                source_url=url,
                display_name=display_name,
                format_selector=format_selector or self.DEFAULT_FORMAT_SELECTOR,
                target_dir=resolved_target_dir,
            )
        )

    def download_now(self, url: str, display_name: str, format_selector: str | None = None) -> DownloadTask:
        """创建下载任务并立刻执行，供 GUI 的单视频下载按钮直接调用。"""

        task_id = self.queue_url(
            url=url,
            display_name=display_name,
            format_selector=format_selector,
        )
        return self.run_task(task_id)

    def queue_video(
        self,
        video: VideoRecord,
        format_selector: str | None = None,
        *,
        source: SourceRecord | None = None,
    ) -> tuple[int | None, bool]:
        """把一个资源库视频加入下载队列，返回任务 ID 和是否为新建。"""

        if video.id is None:
            raise ValueError("Video must be saved before it can be queued.")
        existing = self.repository.find_existing_for_video(video.id)
        if existing is not None:
            return existing.id, False

        source = source or self.source_repository.get_primary_for_video(video.id)
        source_url = video.source_url or f"https://www.bilibili.com/video/{video.bvid}"
        task_id = self.queue_url(
            url=source_url,
            display_name=video.title,
            format_selector=format_selector,
            video_id=video.id,
            target_dir=self._target_dir_for_source(source),
        )
        return task_id, True

    def queue_video_id(
        self,
        video_id: int,
        format_selector: str | None = None,
        *,
        source_id: int | None = None,
    ) -> tuple[int | None, bool]:
        """按本地视频 ID 加入下载队列。"""

        video = self.video_repository.get_by_id(video_id)
        if video is None:
            raise ValueError(f"Video #{video_id} was not found.")
        source = self.source_repository.get_by_id(source_id) if source_id is not None else None
        return self.queue_video(video=video, format_selector=format_selector, source=source)

    def queue_library_videos(self, *, limit: int = 500, format_selector: str | None = None) -> DownloadQueueResult:
        """把资源库最近的视频批量加入下载队列。"""

        return self._queue_videos(self.video_repository.list_all(limit=limit), format_selector=format_selector)

    def queue_source_videos(
        self,
        source_id: int,
        *,
        limit: int = 500,
        format_selector: str | None = None,
    ) -> DownloadQueueResult:
        """把某个来源已同步的视频批量加入下载队列。"""

        source = self.source_repository.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source #{source_id} was not found.")
        return self._queue_videos(
            self.video_repository.list_by_source(source_id=source_id, limit=limit),
            format_selector=format_selector,
            source=source,
        )

    def _queue_videos(
        self,
        videos: list[VideoRecord],
        *,
        format_selector: str | None = None,
        source: SourceRecord | None = None,
    ) -> DownloadQueueResult:
        """批量入队并跳过已存在任务。"""

        task_ids: list[int] = []
        skipped_count = 0
        for video in videos:
            task_id, created = self.queue_video(video=video, format_selector=format_selector, source=source)
            if created and task_id is not None:
                task_ids.append(task_id)
            else:
                skipped_count += 1

        message = f"已加入 {len(task_ids)} 个下载任务，跳过 {skipped_count} 个已有任务。"
        return DownloadQueueResult(
            queued_count=len(task_ids),
            skipped_count=skipped_count,
            task_ids=tuple(task_ids),
            message=message,
        )

    def _target_dir_for_source(self, source: SourceRecord | None) -> Path:
        """按资源库导入来源创建下载子目录；没有来源信息时使用总下载目录。"""

        if source is None:
            return self.paths.downloads_dir
        folder_name = self._safe_folder_name(source.display_name or source.source_key or f"source-{source.id or 'unknown'}")
        return self.paths.downloads_dir / folder_name

    def target_dir_for_source_id(self, source_id: int | None) -> Path:
        """按资源库来源 ID 计算下载目录，供 GUI 单视频格式选择弹窗复用。"""

        source = self.source_repository.get_by_id(source_id) if source_id is not None else None
        return self._target_dir_for_source(source)

    def _safe_folder_name(self, raw_name: str) -> str:
        """把来源名称整理成 Windows 可用的文件夹名。"""

        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", raw_name).strip(" ._")
        if not cleaned:
            cleaned = "source"
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{index}" for index in range(1, 10)),
            *(f"LPT{index}" for index in range(1, 10)),
        }
        if cleaned.upper() in reserved_names:
            cleaned = f"{cleaned}_source"
        return cleaned[:80]

    def run_task(self, task_id: int) -> DownloadTask:
        """按任务 ID 执行一次真实下载，并把进度持续写回数据库。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status in {DownloadStatus.PAUSED, DownloadStatus.CANCELED}:
            return task

        cookie_file_path: Path | None = None
        self._cancel_requests.discard(task_id)
        self.repository.update_runtime(
            task_id,
            status=DownloadStatus.RUNNING,
            progress=0.0,
            error_message=None,
        )
        self._progress_cache[task_id] = 0
        try:
            cookie_file_path = self._build_cookie_file()
            task = self.repository.get_by_id(task_id)
            if task is None:
                raise ValueError(f"Download task #{task_id} disappeared before execution.")

            result = self.adapter.download(
                task,
                cookie_file_path=cookie_file_path,
                progress_hook=lambda payload: self._handle_progress(task_id, payload),
            )
        except DownloadCancelledError as exc:
            self.repository.update_runtime(
                task_id,
                status=DownloadStatus.CANCELED,
                error_message=str(exc),
            )
        except Exception as exc:
            self.repository.update_runtime(
                task_id,
                status=DownloadStatus.FAILED,
                error_message=str(exc),
            )
        else:
            current_task = self.repository.get_by_id(task_id)
            if task_id in self._cancel_requests or (current_task is not None and current_task.status is DownloadStatus.CANCELED):
                self.repository.update_runtime(
                    task_id,
                    status=DownloadStatus.CANCELED,
                    error_message="用户已取消下载。",
                )
            else:
                self.repository.update_runtime(
                    task_id,
                    status=DownloadStatus.SUCCESS,
                    file_path=result.file_path,
                    progress=100.0,
                    error_message=None,
                )
        finally:
            self._progress_cache.pop(task_id, None)
            self._cancel_requests.discard(task_id)
            if cookie_file_path is not None and cookie_file_path.exists():
                cookie_file_path.unlink(missing_ok=True)

        finished_task = self.repository.get_by_id(task_id)
        if finished_task is None:
            raise ValueError(f"Download task #{task_id} could not be loaded after execution.")
        return finished_task

    def run_next(self) -> DownloadTask | None:
        """执行队列中的下一个待下载任务。"""

        tasks = self.repository.list_by_statuses([DownloadStatus.PENDING], limit=1)
        if not tasks:
            return None
        if tasks[0].id is None:
            return None
        return self.run_task(tasks[0].id)

    def run_queue(self, *, limit: int = 0) -> list[DownloadTask]:
        """顺序执行下载队列，limit<=0 表示一直跑到没有 pending 任务。"""

        completed: list[DownloadTask] = []
        while True:
            if limit > 0 and len(completed) >= limit:
                break
            task = self.run_next()
            if task is None:
                break
            completed.append(task)
        return completed

    def retry_task(self, task_id: int) -> DownloadTask:
        """把失败任务重置为 pending，供队列再次执行。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is not DownloadStatus.FAILED:
            raise ValueError("只有失败的下载任务可以重试。")
        self.repository.update_runtime(
            task_id,
            status=DownloadStatus.PENDING,
            progress=0.0,
            error_message=None,
        )
        updated = self.repository.get_by_id(task_id)
        if updated is None:
            raise ValueError(f"Download task #{task_id} could not be loaded after retry reset.")
        return updated

    def update_task_format(self, task_id: int, format_selector: str) -> DownloadTask:
        """为尚未完成的下载任务重新选择格式，供右键菜单和资源库单视频入口复用。"""

        normalized_selector = (format_selector or self.DEFAULT_FORMAT_SELECTOR).strip()
        if not normalized_selector:
            normalized_selector = self.DEFAULT_FORMAT_SELECTOR

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is DownloadStatus.RUNNING:
            raise ValueError("正在下载的任务不能安全修改格式，请等待本轮下载结束后再调整。")
        if task.status is DownloadStatus.SUCCESS:
            raise ValueError("已完成的任务不能直接修改格式；如需重新下载，请先删除该任务记录后再加入队列。")

        next_status = DownloadStatus.PENDING if task.status in {DownloadStatus.FAILED, DownloadStatus.CANCELED} else task.status
        self.repository.update_format_selector(
            task_id,
            normalized_selector,
            status=next_status,
            reset_runtime=task.status in {DownloadStatus.FAILED, DownloadStatus.CANCELED},
        )
        updated = self.repository.get_by_id(task_id)
        if updated is None:
            raise ValueError(f"Download task #{task_id} could not be loaded after format update.")
        return updated

    def pause_task(self, task_id: int) -> DownloadTask:
        """暂停尚未开始的下载任务。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is DownloadStatus.RUNNING:
            raise ValueError("正在下载的 yt-dlp 任务不能安全暂停，请等待本轮下载结束后再处理。")
        if task.status is DownloadStatus.PENDING:
            self.repository.set_status(task_id, DownloadStatus.PAUSED)
        return self.repository.get_by_id(task_id) or task

    def resume_task(self, task_id: int) -> DownloadTask:
        """恢复暂停中的下载任务。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is DownloadStatus.PAUSED:
            self.repository.set_status(task_id, DownloadStatus.PENDING)
        return self.repository.get_by_id(task_id) or task

    def cancel_task(self, task_id: int) -> DownloadTask:
        """取消尚未完成的下载任务。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is DownloadStatus.RUNNING:
            self._cancel_requests.add(task_id)
            self.repository.set_status(
                task_id,
                DownloadStatus.CANCELED,
                error_message="用户请求取消下载，正在等待 yt-dlp 安全中断。",
            )
            return self.repository.get_by_id(task_id) or task
        if task.status not in {DownloadStatus.SUCCESS, DownloadStatus.CANCELED}:
            self.repository.set_status(task_id, DownloadStatus.CANCELED)
        return self.repository.get_by_id(task_id) or task

    def delete_task_record(self, task_id: int) -> None:
        """删除下载任务记录，不删除磁盘文件。"""

        task = self.repository.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Download task #{task_id} was not found.")
        if task.status is DownloadStatus.RUNNING:
            raise ValueError("正在下载的任务不能删除，请等待本轮下载结束后再处理。")
        self.repository.delete(task_id)

    def list_tasks(self, limit: int = 100) -> list[DownloadTask]:
        """读取下载任务队列。"""

        return self.repository.list_all(limit=limit)

    def get_ffmpeg_status(self):
        """返回当前下载环境中的 ffmpeg 可用状态。"""

        return self.adapter.inspect_ffmpeg()

    def probe_video_formats(self, raw_value: str) -> VideoFormatProbeResult:
        """对单视频输入做一次低频格式探测，返回真实可用的格式列表。"""

        preview = self.source_service_preview_video(raw_value=raw_value)
        cookie_file_path = self._build_cookie_file()
        try:
            # Reuse the same URL normalization and exported session path as the real download flow.
            return self.adapter.probe_formats(
                preview.canonical_url or raw_value,
                cookie_file_path=cookie_file_path,
            )
        finally:
            if cookie_file_path is not None and cookie_file_path.exists():
                cookie_file_path.unlink(missing_ok=True)

    def source_service_preview_video(self, raw_value: str) -> SourcePreview:
        """统一复用视频输入解析，避免下载和探测各自写一套 BV 解析。"""

        return self.parser.preview(kind=SourceKind.VIDEO, raw_value=raw_value)

    def _handle_progress(self, task_id: int, payload: dict) -> None:
        """把 yt-dlp 回调转换成较稳定的百分比进度。"""

        if task_id in self._cancel_requests:
            raise DownloadCancelledError("用户已取消下载。")

        status = payload.get("status")
        if status == "finished":
            self.repository.update_runtime(
                task_id,
                status=DownloadStatus.RUNNING,
                progress=99.0,
                file_path=payload.get("filename"),
                error_message=None,
            )
            self._progress_cache[task_id] = 99
            return

        if status != "downloading":
            return

        total_bytes = payload.get("total_bytes") or payload.get("total_bytes_estimate")
        downloaded_bytes = payload.get("downloaded_bytes") or 0
        if not total_bytes:
            return

        progress = max(0, min(99, int(downloaded_bytes * 100 / total_bytes)))
        if self._progress_cache.get(task_id) == progress:
            return

        self._progress_cache[task_id] = progress
        self.repository.update_runtime(
            task_id,
            status=DownloadStatus.RUNNING,
            progress=float(progress),
            error_message=None,
        )

    def _build_cookie_file(self) -> Path | None:
        """把本地登录会话转换成临时 cookie 文件，供 yt-dlp 可选复用。"""

        import os

        session = self.auth_session_repository.get_active()
        if session is None:
            return None

        try:
            cookies = json.loads(session.cookie_json)
        except (TypeError, ValueError):
            return None
        if not isinstance(cookies, dict) or not cookies:
            return None

        file_descriptor, raw_path = tempfile.mkstemp(prefix="bilibili_tool_", suffix=".cookies.txt")
        cookie_path = Path(raw_path)
        try:
            os.close(file_descriptor)
        except OSError:
            pass

        lines = ["# Netscape HTTP Cookie File"]
        for name, value in sorted(cookies.items()):
            if not value:
                continue
            lines.append("\t".join([".bilibili.com", "TRUE", "/", "TRUE", "0", str(name), str(value)]))
        cookie_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return cookie_path


class AuthService:
    """登录状态服务。"""

    def __init__(self, repository: AuthSessionRepository, client: BilibiliClient) -> None:
        self.repository = repository
        self.client = client

    def save_session(self, session_name: str, cookie_json: str, csrf: str | None = None) -> int:
        """保存一份本地会话，为二维码登录落库预留接口。"""

        json.loads(cookie_json)
        return self.repository.upsert(
            AuthSession(
                session_name=session_name,
                cookie_json=cookie_json,
                csrf=csrf,
                is_active=True,
                updated_at=datetime.now(),
            )
        )

    def get_login_state(self) -> LoginState:
        """把底层会话转换成更适合界面展示的状态对象。"""

        session = self.repository.get_active()
        if session is None:
            return LoginState(
                is_logged_in=False,
                session_name="未登录",
                display_message="当前没有可用的 B 站登录态。",
            )
        return LoginState(
            is_logged_in=True,
            session_name=session.session_name,
            display_message="已检测到本地登录会话，后续同步和下载会优先复用它。",
        )

    def build_qr_login_draft(self) -> QrLoginDraft:
        """返回二维码登录的本地流程预览。"""

        return self.client.build_qr_login_draft()

    def init_qr_login(self) -> QrLoginInitResult:
        """真实请求一次二维码初始化接口。"""

        return self.client.init_qr_login()

    def poll_qr_login(self, qrcode_key: str) -> QrLoginPollResult:
        """单次查询二维码状态，不做自动轮询。"""

        if not qrcode_key.strip():
            raise ValueError("QR login key cannot be empty.")
        return self.client.poll_qr_login(qrcode_key.strip())


class BrowserSessionService:
    """浏览器会话服务，负责判断 Cookie 是否齐全并保存到本地。"""

    REQUIRED_COOKIE_NAMES = ("SESSDATA", "bili_jct", "DedeUserID")

    def __init__(self, repository: AuthSessionRepository) -> None:
        self.repository = repository

    def build_snapshot(self, cookies: dict[str, str]) -> BrowserSessionSnapshot:
        """根据当前捕获到的 Cookie 构建浏览器会话快照。"""

        normalized = {key: value for key, value in cookies.items() if value}
        missing = tuple(name for name in self.REQUIRED_COOKIE_NAMES if name not in normalized)
        return BrowserSessionSnapshot(
            cookie_count=len(normalized),
            has_sessdata="SESSDATA" in normalized,
            has_csrf="bili_jct" in normalized,
            has_user_id="DedeUserID" in normalized,
            is_ready=not missing,
            missing_cookie_names=missing,
            cookie_json=json.dumps(normalized, ensure_ascii=False, sort_keys=True),
        )

    def save_captured_session(self, session_name: str, cookies: dict[str, str]) -> int:
        """把浏览器里捕获到的 Cookie 保存成本地会话。"""

        snapshot = self.build_snapshot(cookies)
        if not snapshot.is_ready:
            raise ValueError(f"Missing required cookies: {', '.join(snapshot.missing_cookie_names)}")
        return self.repository.upsert(
            AuthSession(
                session_name=session_name,
                cookie_json=snapshot.cookie_json,
                csrf=cookies.get("bili_jct"),
                is_active=True,
                updated_at=datetime.now(),
            )
        )


class SettingsService:
    """应用设置服务，当前负责界面语言设置。"""

    def __init__(self, paths: AppPaths, settings: AppSettings) -> None:
        self.paths = paths
        self.settings = settings

    def get_ui_language(self) -> str:
        """返回当前生效的界面语言。"""

        return self.settings.ui_language

    def set_ui_language(self, language: str) -> AppSettings:
        """保存界面语言设置，并更新当前运行时配置。"""

        updated = replace(self.settings, ui_language=normalize_ui_language(language))
        saved = save_settings(self.paths, updated)
        self.settings = saved
        return saved

    def set_download_concurrency(self, value: int) -> AppSettings:
        """保存下载并发数量，并限制在桌面端可控范围内。"""

        normalized_value = max(1, min(8, int(value)))
        updated = replace(self.settings, download_concurrency=normalized_value)
        saved = save_settings(self.paths, updated)
        self.settings = saved
        return saved

    def dismiss_login_intro(self) -> AppSettings:
        """关闭登录页首次提示，并把结果写入本地设置。"""

        updated = replace(self.settings, show_login_intro_dialog=False)
        saved = save_settings(self.paths, updated)
        self.settings = saved
        return saved


class DashboardService:
    """首页统计服务。"""

    def __init__(
        self,
        source_service: SourceService,
        library_service: LibraryService,
        download_service: DownloadService,
        auth_service: AuthService,
    ) -> None:
        self.source_service = source_service
        self.library_service = library_service
        self.download_service = download_service
        self.auth_service = auth_service

    def build_summary(self) -> DashboardSummary:
        """聚合首页需要的统计数字。"""

        login_state = self.auth_service.get_login_state()
        return DashboardSummary(
            source_count=len(self.source_service.list_sources()),
            video_count=len(self.library_service.list_videos(limit=500)),
            download_count=len(self.download_service.list_tasks(limit=500)),
            active_session_name=login_state.session_name,
        )


@dataclass(slots=True)
class AppContext:
    """把运行期依赖聚合起来，作为整个程序的组合根。"""

    paths: AppPaths
    settings: AppSettings
    database: Database
    bilibili_client: BilibiliClient
    user_archive_scraper: BrowserUserArchiveScraper
    browser_user_search: BrowserUserSearch
    auth_session_repository: AuthSessionRepository
    source_repository: SourceRepository
    video_repository: VideoRepository
    sync_task_repository: SyncTaskRepository
    download_task_repository: DownloadTaskRepository
    workspace_service: WorkspaceService
    auth_service: AuthService
    browser_session_service: BrowserSessionService
    settings_service: SettingsService
    source_service: SourceService
    library_service: LibraryService
    download_service: DownloadService
    dashboard_service: DashboardService


def build_context(root: Path | None = None) -> AppContext:
    """构建应用上下文，供 CLI、GUI 和 worker 共享。"""

    paths = build_app_paths(root=root)
    settings = load_settings(paths)
    database = Database(paths.database_path)
    bilibili_client = BilibiliClient(settings=settings)
    user_archive_scraper = BrowserUserArchiveScraper(user_agent=settings.user_agent)
    browser_user_search = BrowserUserSearch(user_agent=settings.user_agent)

    auth_session_repository = AuthSessionRepository(database)
    source_repository = SourceRepository(database)
    video_repository = VideoRepository(database)
    sync_task_repository = SyncTaskRepository(database)
    download_task_repository = DownloadTaskRepository(database)

    workspace_service = WorkspaceService(paths=paths, database=database)
    auth_service = AuthService(repository=auth_session_repository, client=bilibili_client)
    browser_session_service = BrowserSessionService(repository=auth_session_repository)
    settings_service = SettingsService(paths=paths, settings=settings)
    source_service = SourceService(
        parser=SourceInputParser(),
        repository=source_repository,
        video_repository=video_repository,
        sync_task_repository=sync_task_repository,
        client=bilibili_client,
        auth_session_repository=auth_session_repository,
        user_archive_scraper=user_archive_scraper,
        browser_user_search=browser_user_search,
    )
    library_service = LibraryService(video_repository=video_repository)
    download_service = DownloadService(
        parser=SourceInputParser(),
        repository=download_task_repository,
        auth_session_repository=auth_session_repository,
        video_repository=video_repository,
        source_repository=source_repository,
        paths=paths,
        adapter=YtDlpAdapter(user_agent=settings.user_agent),
    )
    dashboard_service = DashboardService(
        source_service=source_service,
        library_service=library_service,
        download_service=download_service,
        auth_service=auth_service,
    )

    return AppContext(
        paths=paths,
        settings=settings,
        database=database,
        bilibili_client=bilibili_client,
        user_archive_scraper=user_archive_scraper,
        browser_user_search=browser_user_search,
        auth_session_repository=auth_session_repository,
        source_repository=source_repository,
        video_repository=video_repository,
        sync_task_repository=sync_task_repository,
        download_task_repository=download_task_repository,
        workspace_service=workspace_service,
        auth_service=auth_service,
        browser_session_service=browser_session_service,
        settings_service=settings_service,
        source_service=source_service,
        library_service=library_service,
        download_service=download_service,
        dashboard_service=dashboard_service,
    )
