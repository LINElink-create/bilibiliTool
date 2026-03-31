from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.entities import VideoItem


class BaseCrawler(ABC):
    @abstractmethod
    def crawl_uid(self, uid: str, include_detail: bool = False) -> list[VideoItem]:
        raise NotImplementedError
