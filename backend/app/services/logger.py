# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Настройка логирования приложения.

Все записи пишутся в DATA_DIR/app.log с ротацией (2 МБ x 3 файла).
Перехватываются непойманные исключения потоков и фоновых задач.
"""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from app.config import DATA_DIR

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DATA_DIR / "app.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root.addHandler(handler)

    def thread_excepthook(args: threading.ExceptHookArgs) -> None:
        logging.getLogger("zelvera").error(
            "Непойманное исключение в потоке: %s",
            args.exc_info[1],
            exc_info=args.exc_info,
        )

    threading.excepthook = thread_excepthook

    return logging.getLogger("zelvera")


def clear_log() -> None:
    """Очищает файл журнала app.log, сохраняя открытый handler активным."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if isinstance(handler, RotatingFileHandler) and handler.stream:
            try:
                handler.stream.seek(0)
                handler.stream.truncate(0)
                handler.stream.flush()
            except Exception:
                continue


logger = setup_logging()
