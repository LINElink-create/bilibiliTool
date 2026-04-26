from __future__ import annotations

import tempfile
import unittest
import logging
from pathlib import Path

from bilibili_tool.application import build_context
from bilibili_tool.domain import DownloadStatus, FavoriteFetchResult, VideoRecord
from bilibili_tool.infra.download.ytdlp_adapter import DownloadExecutionResult


class FakeBilibiliClient:
    def __init__(self) -> None:
        self.cookies = {}

    def set_cookies(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies

    def fetch_favorite_page(self, favorite_id: str, *, page: int, page_size: int) -> FavoriteFetchResult:
        if page == 1:
            return FavoriteFetchResult(
                success=True,
                favorite_id=favorite_id,
                title="测试收藏夹",
                owner_name="tester",
                message="page 1",
                videos=(
                    VideoRecord(bvid="BV1111111111", title="视频 1", source_url="https://www.bilibili.com/video/BV1111111111"),
                    VideoRecord(bvid="BV2222222222", title="视频 2", source_url="https://www.bilibili.com/video/BV2222222222"),
                ),
            )
        return FavoriteFetchResult(
            success=True,
            favorite_id=favorite_id,
            title="测试收藏夹",
            owner_name="tester",
            message="page 2",
            videos=(VideoRecord(bvid="BV3333333333", title="视频 3", source_url="https://www.bilibili.com/video/BV3333333333"),),
        )


class FakeUserArchiveScraper:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []
        self.cookies = {}

    def set_cookies(self, cookies: dict[str, str]) -> None:
        self.cookies = cookies

    def fetch_page(self, uid: str, *, page: int, page_size: int) -> FavoriteFetchResult:
        self.calls.append((uid, page, page_size))
        if page > 2:
            return FavoriteFetchResult(
                success=True,
                favorite_id=uid,
                title="测试 UP",
                owner_name="tester",
                message="empty",
                videos=(),
            )
        bvid = "BV6666666666" if page == 1 else "BV7777777777"
        return FavoriteFetchResult(
            success=True,
            favorite_id=uid,
            title="测试 UP",
            owner_name="tester",
            message=f"page {page}",
            videos=(
                VideoRecord(
                    bvid=bvid,
                    title=f"网页抓取投稿 {page}",
                    owner_uid=uid,
                    owner_name="tester",
                    source_url=f"https://www.bilibili.com/video/{bvid}",
                ),
            ),
        )


class FakeDownloadAdapter:
    def inspect_ffmpeg(self):
        return None

    def download(self, task, *, cookie_file_path=None, progress_hook=None):
        if progress_hook is not None:
            progress_hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 2})
            progress_hook({"status": "finished", "filename": str(Path(task.target_dir or ".") / "done.mp4")})
        return DownloadExecutionResult(file_path=str(Path(task.target_dir or ".") / "done.mp4"))


class ServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        logging.shutdown()

    def test_sync_favorite_all_writes_multiple_pages(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            context = build_context(root=Path(tmpdir))
            context.workspace_service.initialize()
            context.source_service.client = FakeBilibiliClient()

            result = context.source_service.sync_favorite_all("123", page_size=2, max_pages=5)

            self.assertTrue(result.success)
            self.assertEqual(result.page_count, 2)
            self.assertEqual(result.synced_count, 3)
            self.assertEqual(len(context.library_service.list_videos()), 3)

    def test_sync_user_archive_uses_browser_scraper(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            context = build_context(root=Path(tmpdir))
            context.workspace_service.initialize()
            scraper = FakeUserArchiveScraper()
            context.source_service.user_archive_scraper = scraper

            result = context.source_service.sync_user_archive("546195", page_size=30, max_pages=5)

            self.assertTrue(result.success)
            self.assertEqual(result.page_count, 2)
            self.assertEqual(result.synced_count, 2)
            self.assertEqual(scraper.calls[0], ("546195", 1, 30))
            self.assertEqual(scraper.calls[1], ("546195", 2, 30))
            self.assertEqual(scraper.calls[2], ("546195", 3, 30))
            self.assertEqual(len(context.library_service.list_videos()), 2)

    def test_queue_library_skips_existing_tasks_and_controls_status(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            context = build_context(root=Path(tmpdir))
            context.workspace_service.initialize()
            video_id, _ = context.video_repository.upsert(
                VideoRecord(
                    bvid="BV4444444444",
                    title="可下载视频",
                    source_url="https://www.bilibili.com/video/BV4444444444",
                )
            )

            first = context.download_service.queue_library_videos()
            second = context.download_service.queue_library_videos()

            self.assertEqual(first.queued_count, 1)
            self.assertEqual(second.queued_count, 0)
            self.assertEqual(second.skipped_count, 1)

            task_id = first.task_ids[0]
            paused = context.download_service.pause_task(task_id)
            self.assertEqual(paused.status.value, "paused")
            resumed = context.download_service.resume_task(task_id)
            self.assertEqual(resumed.status.value, "pending")
            canceled = context.download_service.cancel_task(task_id)
            self.assertEqual(canceled.status.value, "canceled")
            self.assertEqual(context.download_task_repository.get_by_id(task_id).video_id, video_id)

            context.download_task_repository.update_runtime(
                task_id,
                status=DownloadStatus.FAILED,
                error_message="boom",
            )
            retried = context.download_service.queue_library_videos()
            self.assertEqual(retried.queued_count, 1)
            self.assertNotEqual(retried.task_ids[0], task_id)

    def test_run_queue_uses_pending_tasks(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            context = build_context(root=Path(tmpdir))
            context.workspace_service.initialize()
            context.download_service.adapter = FakeDownloadAdapter()
            context.download_service.queue_url(
                url="https://www.bilibili.com/video/BV5555555555",
                display_name="立即下载",
            )

            tasks = context.download_service.run_queue()

            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].status.value, "success")
            self.assertEqual(tasks[0].progress, 100.0)


if __name__ == "__main__":
    unittest.main()
