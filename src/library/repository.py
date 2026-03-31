from __future__ import annotations

from typing import Optional

from src.infra.database import Database
from src.models.entities import DownloadTask, MediaFile, PlayHistory, VideoItem


class LibraryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_video(self, video: VideoItem) -> int:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO videos (
                    source, uid, user_name, bv, url, title, play, duration, pub_date,
                    collected_at, danmu, video_type, page_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    source=excluded.source,
                    uid=excluded.uid,
                    user_name=excluded.user_name,
                    bv=excluded.bv,
                    title=excluded.title,
                    play=excluded.play,
                    duration=excluded.duration,
                    pub_date=excluded.pub_date,
                    collected_at=excluded.collected_at,
                    danmu=excluded.danmu,
                    video_type=excluded.video_type,
                    page_count=excluded.page_count,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    video.source,
                    video.uid,
                    video.user_name,
                    video.bv,
                    video.url,
                    video.title,
                    video.play,
                    video.duration,
                    video.pub_date,
                    video.collected_at,
                    video.danmu,
                    video.video_type,
                    video.page_count,
                ),
            )
            row = connection.execute("SELECT id FROM videos WHERE url = ?", (video.url,)).fetchone()
            return int(row["id"])

    def list_videos(self, limit: int = 50) -> list[VideoItem]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, source, uid, user_name, bv, url, title, play, duration, pub_date,
                       collected_at, danmu, video_type, page_count
                FROM videos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            VideoItem(
                id=row["id"],
                source=row["source"],
                uid=row["uid"],
                user_name=row["user_name"],
                bv=row["bv"],
                url=row["url"],
                title=row["title"],
                play=row["play"],
                duration=row["duration"],
                pub_date=row["pub_date"],
                collected_at=row["collected_at"],
                danmu=row["danmu"],
                video_type=row["video_type"],
                page_count=row["page_count"],
            )
            for row in rows
        ]

    def create_download(self, task: DownloadTask) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO downloads (
                    video_id, status, target_dir, format_selector, downloader, output_path, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.video_id,
                    task.status,
                    task.target_dir,
                    task.format_selector,
                    task.downloader,
                    task.output_path,
                    task.error_message,
                ),
            )
            return int(cursor.lastrowid)

    def update_download_status(
        self,
        download_id: int,
        status: str,
        output_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE downloads
                SET status = ?, output_path = COALESCE(?, output_path),
                    error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, output_path, error_message, download_id),
            )

    def upsert_media_file(self, media_file: MediaFile) -> int:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO media_files (
                    video_id, file_path, file_size, duration_seconds, container, video_codec, audio_codec
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    video_id=excluded.video_id,
                    file_size=excluded.file_size,
                    duration_seconds=excluded.duration_seconds,
                    container=excluded.container,
                    video_codec=excluded.video_codec,
                    audio_codec=excluded.audio_codec,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    media_file.video_id,
                    media_file.file_path,
                    media_file.file_size,
                    media_file.duration_seconds,
                    media_file.container,
                    media_file.video_codec,
                    media_file.audio_codec,
                ),
            )
            row = connection.execute(
                "SELECT id FROM media_files WHERE file_path = ?",
                (media_file.file_path,),
            ).fetchone()
            return int(row["id"])

    def save_play_history(self, history: PlayHistory) -> int:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO play_history (media_file_id, position_seconds, play_count, completed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(media_file_id) DO UPDATE SET
                    position_seconds=excluded.position_seconds,
                    play_count=excluded.play_count,
                    completed=excluded.completed,
                    last_played_at=CURRENT_TIMESTAMP
                """,
                (
                    history.media_file_id,
                    history.position_seconds,
                    history.play_count,
                    int(history.completed),
                ),
            )
            row = connection.execute(
                "SELECT id FROM play_history WHERE media_file_id = ?",
                (history.media_file_id,),
            ).fetchone()
            return int(row["id"])

    def set_setting(self, key: str, value: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def get_setting(self, key: str) -> Optional[str]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])
