# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Быстрый старт Zelvera: python run.py

По умолчанию сервер слушает 0.0.0.0:8000 без автоперезагрузки — это
безопасный режим для контейнера/сервиса. Для разработки включите
автоперезагрузку переменной ZELVERA_DEV=1.
"""
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    uvicorn.run(
        "app.main:app",
        host=(os.getenv("ZELVERA_HOST") or "0.0.0.0").strip(),
        port=int((os.getenv("ZELVERA_PORT") or "8000").strip()),
        reload=_env_flag("ZELVERA_DEV"),
    )
