from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.infra.download import YtDlpAdapter


@dataclass(slots=True)
class DownloadWorker:
    """下载 worker 入口，占位给下一阶段接上任务队列。"""

    adapter: YtDlpAdapter

    def run_once(self) -> None:
        """下一阶段会在这里消费数据库里的下载任务。"""

        raise NotImplementedError("Download worker is planned for the next milestone.")

