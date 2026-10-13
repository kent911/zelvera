# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Десктопный запуск Zelvera.

Запускает локальный сервер (FastAPI) в фоновом потоке и открывает окно
pywebview. Если GUI-бэкенд недоступен, открывает приложение в браузере.

Использование: python desktop.py
"""
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

import uvicorn

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Прямой импорт заставляет PyInstaller упаковать пакет app в сборку
# (uvicorn стартует сервер по строковому пути "app.main:app").
from app.main import app as _app_  # noqa: E402, F401

try:
    import webview
except Exception:  # отсутствует GUI-бэкенд (GTK и т.п.)
    webview = None

APP_TITLE = "Zelvera — локальный медицинский ИИ"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_up(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(f"http://127.0.0.1:{port}/api/auth/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main() -> None:
    port = free_port()
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not wait_until_up(port):
        print("Не удалось запустить локальный сервер.", flush=True)
        return

    url = f"http://127.0.0.1:{port}"

    if webview is not None and getattr(webview, "guilib", None):
        webview.create_window(
            APP_TITLE,
            url,
            width=1200,
            height=820,
            min_size=(900, 600),
        )
        webview.start()
        print("Окно закрыто, сервер остановлен.", flush=True)
    else:
        print("GUI-бэкенд pywebview недоступен. Открываю приложение в браузере.", flush=True)
        print(f"Адрес: {url}", flush=True)
        webbrowser.open(url)
        print("Для остановки нажмите Ctrl+C.", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
