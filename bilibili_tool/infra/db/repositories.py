from __future__ import annotations

from datetime import datetime

from bilibili_tool.domain.entities import AuthSession, DownloadTask, SourceRecord, SyncTask, VideoRecord
from bilibili_tool.domain.enums import DownloadStatus, SourceKind, SyncTaskStatus
from bilibili_tool.infra.db.database import Database


def _parse_datetime(value: str | None) -> datetime | None:
    """把 SQLite 里的文本时间统一转换成 datetime。"""

    if not value:
        return None
    return datetime.fromisoformat(value.replace(" ", "T"))


class AuthSessionRepository:
    """负责登录会话的增删查改。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, session: AuthSession) -> int:
        """按会话名去重写入登录态。"""

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (session_name, cookie_json, csrf, is_active, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_name) DO UPDATE SET
                    cookie_json=excluded.cookie_json,
                    csrf=excluded.csrf,
                    is_active=excluded.is_active,
                    expires_at=excluded.expires_at,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session.session_name,
                    session.cookie_json,
                    session.csrf,
                    int(session.is_active),
                    session.expires_at.isoformat(sep=" ") if session.expires_at else None,
                ),
            )
            row = connection.execute(
                "SELECT id FROM auth_sessions WHERE session_name = ?",
                (session.session_name,),
            ).fetchone()
            return int(row["id"])

    def get_active(self) -> AuthSession | None:
        """读取当前激活的登录会话。"""

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, session_name, cookie_json, csrf, is_active, created_at, updated_at, expires_at
                FROM auth_sessions
                WHERE is_active = 1
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return AuthSession(
            id=row["id"],
            session_name=row["session_name"],
            cookie_json=row["cookie_json"],
            csrf=row["csrf"],
            is_active=bool(row["is_active"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            expires_at=_parse_datetime(row["expires_at"]),
        )


class SourceRepository:
    """负责来源表的增删查改。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, source: SourceRecord) -> int:
        """按来源类型和 key 去重写入。"""

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (kind, source_key, display_name, url, is_enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(kind, source_key) DO UPDATE SET
                    display_name=excluded.display_name,
                    url=excluded.url,
                    is_enabled=excluded.is_enabled,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (source.kind.value, source.source_key, source.display_name, source.url, int(source.is_enabled)),
            )
            row = connection.execute(
                "SELECT id FROM sources WHERE kind = ? AND source_key = ?",
                (source.kind.value, source.source_key),
            ).fetchone()
            return int(row["id"])

    def list_all(self) -> list[SourceRecord]:
        """返回来源列表，供 CLI 和 GUI 共用。"""

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, kind, source_key, display_name, url, is_enabled, created_at, updated_at, last_sync_at
                FROM sources
                ORDER BY id DESC
                """
            ).fetchall()
        return [
            SourceRecord(
                id=row["id"],
                kind=SourceKind(row["kind"]),
                source_key=row["source_key"],
                display_name=row["display_name"],
                url=row["url"],
                is_enabled=bool(row["is_enabled"]),
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
                last_sync_at=_parse_datetime(row["last_sync_at"]),
            )
            for row in rows
        ]

    def get_by_id(self, source_id: int) -> SourceRecord | None:
        """按主键读取单个来源。"""

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, kind, source_key, display_name, url, is_enabled, created_at, updated_at, last_sync_at
                FROM sources
                WHERE id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return SourceRecord(
            id=row["id"],
            kind=SourceKind(row["kind"]),
            source_key=row["source_key"],
            display_name=row["display_name"],
            url=row["url"],
            is_enabled=bool(row["is_enabled"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            last_sync_at=_parse_datetime(row["last_sync_at"]),
        )

    def mark_synced(self, source_id: int) -> None:
        """记录来源最近一次同步时间。"""

        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE sources
                SET last_sync_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (source_id,),
            )


class VideoRepository:
    """负责视频元数据和来源关联。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, video: VideoRecord) -> tuple[int, bool]:
        """按 bvid 去重写入视频元数据，并返回是否为新增记录。"""

        with self.database.connect() as connection:
            existing = connection.execute("SELECT id FROM videos WHERE bvid = ?", (video.bvid,)).fetchone()
            connection.execute(
                """
                INSERT INTO videos (
                    bvid, aid, title, page_count, owner_uid, owner_name, cover_url,
                    description, duration_seconds, pub_time, source_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bvid) DO UPDATE SET
                    aid=excluded.aid,
                    title=excluded.title,
                    page_count=excluded.page_count,
                    owner_uid=excluded.owner_uid,
                    owner_name=excluded.owner_name,
                    cover_url=excluded.cover_url,
                    description=excluded.description,
                    duration_seconds=excluded.duration_seconds,
                    pub_time=excluded.pub_time,
                    source_url=excluded.source_url,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    video.bvid,
                    video.aid,
                    video.title,
                    video.page_count,
                    video.owner_uid,
                    video.owner_name,
                    video.cover_url,
                    video.description,
                    video.duration_seconds,
                    video.pub_time.isoformat(sep=" ") if video.pub_time else None,
                    video.source_url,
                ),
            )
            row = connection.execute("SELECT id FROM videos WHERE bvid = ?", (video.bvid,)).fetchone()
            return int(row["id"]), existing is None

    def link_to_source(self, source_id: int, video_id: int) -> None:
        """保存来源和视频的多对多关系。"""

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_video_links (source_id, video_id)
                VALUES (?, ?)
                ON CONFLICT(source_id, video_id) DO NOTHING
                """,
                (source_id, video_id),
            )

    def list_all(self, limit: int = 100) -> list[VideoRecord]:
        """按最近写入顺序返回视频。"""

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, bvid, aid, title, page_count, owner_uid, owner_name, cover_url,
                       description, duration_seconds, pub_time, source_url, created_at, updated_at
                FROM videos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            VideoRecord(
                id=row["id"],
                bvid=row["bvid"],
                aid=row["aid"],
                title=row["title"],
                page_count=row["page_count"],
                owner_uid=row["owner_uid"],
                owner_name=row["owner_name"],
                cover_url=row["cover_url"],
                description=row["description"],
                duration_seconds=row["duration_seconds"],
                pub_time=_parse_datetime(row["pub_time"]),
                source_url=row["source_url"],
                created_at=_parse_datetime(row["created_at"]),
                updated_at=_parse_datetime(row["updated_at"]),
            )
            for row in rows
        ]


class SyncTaskRepository:
    """管理同步任务状态。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, task: SyncTask) -> int:
        """创建同步任务记录。"""

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sync_tasks (
                    source_id, status, stage, message, started_at, finished_at,
                    items_total, items_new, items_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.source_id,
                    task.status.value,
                    task.stage,
                    task.message,
                    task.started_at.isoformat(sep=" ") if task.started_at else None,
                    task.finished_at.isoformat(sep=" ") if task.finished_at else None,
                    task.items_total,
                    task.items_new,
                    task.items_updated,
                ),
            )
            return int(cursor.lastrowid)

    def list_recent(self, limit: int = 20) -> list[SyncTask]:
        """读取最近同步记录。"""

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, source_id, status, stage, message, started_at, finished_at,
                       items_total, items_new, items_updated
                FROM sync_tasks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            SyncTask(
                id=row["id"],
                source_id=row["source_id"],
                status=SyncTaskStatus(row["status"]),
                stage=row["stage"],
                message=row["message"],
                started_at=_parse_datetime(row["started_at"]),
                finished_at=_parse_datetime(row["finished_at"]),
                items_total=row["items_total"],
                items_new=row["items_new"],
                items_updated=row["items_updated"],
            )
            for row in rows
        ]


class DownloadTaskRepository:
    """管理下载任务队列。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, task: DownloadTask) -> int:
        """创建待下载任务。"""

        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO download_tasks (
                    video_id, source_url, display_name, format_selector, target_dir,
                    status, file_path, progress, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.video_id,
                    task.source_url,
                    task.display_name,
                    task.format_selector,
                    task.target_dir,
                    task.status.value,
                    task.file_path,
                    task.progress,
                    task.error_message,
                ),
            )
            return int(cursor.lastrowid)

    def get_by_id(self, task_id: int) -> DownloadTask | None:
        """按主键读取单个下载任务，供执行器更新运行状态。"""

        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, video_id, source_url, display_name, format_selector, target_dir,
                       status, file_path, progress, error_message, created_at, updated_at
                FROM download_tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_download_task(row)

    def update_runtime(
        self,
        task_id: int,
        *,
        status: DownloadStatus | None = None,
        file_path: str | None = None,
        progress: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """更新下载任务的运行状态、进度和最终输出。"""

        with self.database.connect() as connection:
            current = connection.execute(
                """
                SELECT status, file_path, progress, error_message
                FROM download_tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"Download task #{task_id} was not found.")

            connection.execute(
                """
                UPDATE download_tasks
                SET status = ?,
                    file_path = ?,
                    progress = ?,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    (status or DownloadStatus(current["status"])).value,
                    file_path if file_path is not None else current["file_path"],
                    progress if progress is not None else current["progress"],
                    error_message,
                    task_id,
                ),
            )

    def list_all(self, limit: int = 100) -> list[DownloadTask]:
        """返回下载队列，供 GUI 和 CLI 展示。"""

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, video_id, source_url, display_name, format_selector, target_dir,
                       status, file_path, progress, error_message, created_at, updated_at
                FROM download_tasks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_download_task(row) for row in rows]

    @staticmethod
    def _row_to_download_task(row) -> DownloadTask:
        """把 SQLite 行对象统一转换成 DownloadTask。"""

        return DownloadTask(
            id=row["id"],
            video_id=row["video_id"],
            source_url=row["source_url"],
            display_name=row["display_name"],
            format_selector=row["format_selector"],
            target_dir=row["target_dir"],
            status=DownloadStatus(row["status"]),
            file_path=row["file_path"],
            progress=row["progress"],
            error_message=row["error_message"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )
