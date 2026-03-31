from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import AppPaths, build_app_paths
from src.crawler import BilibiliCrawler
from src.downloader import YtDlpDownloader
from src.infra import Database
from src.library import LibraryRepository
from src.player import MPVPlayer


@dataclass(slots=True)
class AppContext:
    paths: AppPaths
    database: Database
    repository: LibraryRepository
    crawler: BilibiliCrawler
    downloader: YtDlpDownloader
    player: MPVPlayer


def build_context(root: Path | None = None) -> AppContext:
    paths = build_app_paths(root)
    database = Database(paths.database_path)
    repository = LibraryRepository(database)
    crawler = BilibiliCrawler(save_dir=str(paths.export_dir))
    downloader = YtDlpDownloader()
    player = MPVPlayer()
    return AppContext(
        paths=paths,
        database=database,
        repository=repository,
        crawler=crawler,
        downloader=downloader,
        player=player,
    )
