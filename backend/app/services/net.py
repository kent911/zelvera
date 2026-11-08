# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""HTTP-клиенты: запросы к локальной сети идут в обход прокси из окружения.

httpx и OpenAI SDK по умолчанию читают HTTP_PROXY/HTTPS_PROXY/ALL_PROXY и
шлют через них все запросы, включая обращения к Ollama, llama-server и
kiwix-serve на 127.0.0.1 или в LAN. Если прокси лежит, локальные сервисы
становятся «недоступны», хотя работают. Для таких адресов отключаем
переменные окружения (trust_env=False) и ходим напрямую.
"""
import ipaddress
import os
from urllib.parse import urlparse

import httpx

# ZELVERA_PROXY_LAN=1 — вернуть прокси и для локальных адресов (нужно редко).
FORCE_PROXY_FOR_LAN = os.getenv("ZELVERA_PROXY_LAN", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _is_lan_host(host: str) -> bool:
    name = (host or "").strip().strip("[]").lower()
    if not name:
        return False
    if name == "localhost" or name.endswith(".localhost") or name.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(name)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def is_lan_url(url: str) -> bool:
    """True, если адрес ведёт на этот компьютер или в приватную сеть."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    return _is_lan_host(host)


def client_options(url: str) -> dict:
    """Доп. аргументы httpx.AsyncClient: для LAN выключаем прокси из окружения."""
    if FORCE_PROXY_FOR_LAN or not is_lan_url(url):
        return {}
    return {"trust_env": False}


def async_client(url: str, **kwargs) -> httpx.AsyncClient:
    """httpx.AsyncClient, который для LAN-адресов не использует прокси окружения."""
    return httpx.AsyncClient(**{**client_options(url), **kwargs})
