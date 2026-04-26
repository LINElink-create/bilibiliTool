from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from bilibili_tool.infra.db.schema import SCHEMA_SQL


class Database:
    """封装 SQLite 连接、建表和轻量迁移逻辑。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure_parent(self) -> None:
        """数据库目录不存在时自动创建。"""

        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """统一设置 row_factory 和外键约束。"""

        self.ensure_parent()
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('PRAGMA foreign_keys = ON;')
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        """创建基础表，并对第一阶段新增字段做轻量迁移。"""

        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._migrate_videos_table(connection)

    def _migrate_videos_table(self, connection: sqlite3.Connection) -> None:
        """为已有数据库补齐第一阶段新增的 aid 字段。"""

        columns = {
            row['name']
            for row in connection.execute("PRAGMA table_info(videos)").fetchall()
        }
        if 'aid' not in columns:
            connection.execute('ALTER TABLE videos ADD COLUMN aid INTEGER')