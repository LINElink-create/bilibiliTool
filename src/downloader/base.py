from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseDownloader(ABC):
    @abstractmethod
    def build_command(self, url: str, output_dir: Path) -> list[str]:
        raise NotImplementedError
