from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BasePlayer(ABC):
    @abstractmethod
    def build_command(self, media_path: Path) -> list[str]:
        raise NotImplementedError
