from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.application.services import DownloadService
from bilibili_tool.domain import DownloadTask


@dataclass(slots=True)
class DownloadWorker:
    """下载 worker 入口，消费数据库中的 pending 任务。"""

    service: DownloadService

    def run_once(self) -> DownloadTask | None:
        """执行一个 pending 下载任务，没有任务时返回 None。"""

        return self.service.run_next()
