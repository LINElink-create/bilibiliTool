from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.application.services import SourceService
from bilibili_tool.domain import SourceKind, SourceSyncResult


@dataclass(slots=True)
class SyncWorker:
    """同步 worker 入口，按来源类型执行一次分页同步。"""

    service: SourceService

    def run_once(self, kind: SourceKind, value: str, *, max_pages: int = 20) -> SourceSyncResult:
        """同步一个来源。"""

        if kind is SourceKind.USER:
            return self.service.sync_user_archive(value, max_pages=max_pages)
        if kind is SourceKind.FAVORITE:
            return self.service.sync_favorite_all(value, max_pages=max_pages)
        raise ValueError("SyncWorker only supports user and favorite sources.")
