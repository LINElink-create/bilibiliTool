from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from src.gui import run_desktop_app
from src.models import DownloadTask
from src.services import build_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bilibiliTool v1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create local app directories and SQLite database.")

    crawl_parser = subparsers.add_parser("crawl", help="Crawl bilibili videos by UID.")
    crawl_parser.add_argument("--uid", required=True, help="Target bilibili UID")
    crawl_parser.add_argument("--detail", action="store_true", help="Fetch per-video detail pages")
    crawl_parser.add_argument("--save-json", action="store_true", help="Also export crawled records to JSON")

    queue_parser = subparsers.add_parser("queue-download", help="Create a download task for a known video url.")
    queue_parser.add_argument("--url", required=True, help="Video URL already imported into the database")
    queue_parser.add_argument("--format", default="bestvideo+bestaudio/best", help="yt-dlp format selector")

    subparsers.add_parser("list-videos", help="List recent videos from the local library.")
    subparsers.add_parser("desktop", help="Launch the future desktop shell.")
    return parser


def command_init_db() -> int:
    context = build_context()
    context.database.initialize()
    context.paths.export_dir.mkdir(parents=True, exist_ok=True)
    context.paths.downloads_dir.mkdir(parents=True, exist_ok=True)
    print(f"Database initialized at {context.paths.database_path}")
    return 0


def command_crawl(uid: str, include_detail: bool, save_json: bool) -> int:
    context = build_context()
    context.database.initialize()

    videos = context.crawler.crawl_uid(uid, include_detail=include_detail)
    saved_ids: list[int] = []
    for video in videos:
        saved_ids.append(context.repository.upsert_video(video))

    if save_json:
        export_path = context.paths.export_dir / f"{uid}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps([asdict(video) for video in videos], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Exported {len(videos)} videos to {export_path}")

    print(f"Imported {len(saved_ids)} videos for UID {uid}")
    return 0


def command_queue_download(url: str, format_selector: str) -> int:
    context = build_context()
    context.database.initialize()
    videos = context.repository.list_videos(limit=500)
    matched = next((video for video in videos if video.url == url), None)
    if matched is None or matched.id is None:
        print("Video not found in local database. Run the crawl command first.")
        return 1

    download_id = context.repository.create_download(
        DownloadTask(
            video_id=matched.id,
            target_dir=str(context.paths.downloads_dir),
            format_selector=format_selector,
        )
    )
    print(f"Queued download #{download_id} for {matched.title}")
    return 0


def command_list_videos() -> int:
    context = build_context()
    context.database.initialize()
    videos = context.repository.list_videos(limit=20)
    if not videos:
        print("No videos in local library yet.")
        return 0

    for video in videos:
        print(f"[{video.id}] {video.user_name} - {video.title} ({video.url})")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        return command_init_db()
    if args.command == "crawl":
        return command_crawl(args.uid, args.detail, args.save_json)
    if args.command == "queue-download":
        return command_queue_download(args.url, args.format)
    if args.command == "list-videos":
        return command_list_videos()
    if args.command == "desktop":
        context = build_context()
        context.database.initialize()
        return run_desktop_app(context)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
