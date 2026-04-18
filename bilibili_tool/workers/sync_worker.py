from __future__ import annotations

from dataclasses import dataclass

from bilibili_tool.infra.bilibili import BilibiliClient


@dataclass(slots=True)
class SyncWorker:
    """同步 worker 入口，占位给下一阶段接上来源抓取。"""

    client: BilibiliClient

    def run_once(self) -> None:
        """下一阶段会在这里消费来源并写入视频元数据。"""

        raise NotImplementedError("Sync worker is planned for the next milestone.")
