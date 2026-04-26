from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(logs_dir: Path) -> Path:
    """初始化应用日志文件，并避免重复注册 handler。"""

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / 'app.log'

    root_logger = logging.getLogger('bilibili_tool')
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path) for handler in root_logger.handlers):
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return log_path