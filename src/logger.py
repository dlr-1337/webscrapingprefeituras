from __future__ import annotations

import logging
from pathlib import Path

from src.utils import project_path


def configurar_logger(log_path: str | Path | None = None) -> logging.Logger:
    path = Path(log_path) if log_path else project_path("logs", "execucao.log")
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("webscraping_prefeituras")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

