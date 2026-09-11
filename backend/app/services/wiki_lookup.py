# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Справка по одному показателю из офлайн-Википедии (Kiwix) с кешем в БД.

Единая точка поиска для разбора документов и чат-инструментов: результат
(найденная статья либо факт «не найдено») кешируется по паре (ZIM, показатель)
на CACHE_TTL секунд, чтобы повторные запросы не нагружали Kiwix.
"""
import asyncio
import json
from datetime import datetime
from typing import Any

from app.services import database, kiwix

CACHE_TTL = 7 * 24 * 3600      # срок жизни записи кеша, сек (7 дней)
CACHE_SNIPPET_MAX = 1000       # сколько символов статьи хранить в кеше
LOOKUP_TIMEOUT = 15.0          # лимит на один запрос к Kiwix, сек

_DT_FMT = "%Y-%m-%d %H:%M:%S"


def _cache_get(key: str) -> dict[str, Any] | None:
    try:
        with database.get_conn() as conn:
            row = conn.execute(
                "SELECT payload, updated_at FROM wiki_cache WHERE key = ?", (key,)
            ).fetchone()
    except Exception:  # noqa: BLE001 — кеш не критичен
        return None
    if not row:
        return None
    try:
        age = (datetime.now() - datetime.strptime(row["updated_at"], _DT_FMT)).total_seconds()
    except (TypeError, ValueError):
        return None
    if age > CACHE_TTL:
        return None
    try:
        return json.loads(row["payload"])
    except (TypeError, ValueError):
        return None


def _cache_put(key: str, payload: dict[str, Any]) -> None:
    try:
        with database.get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO wiki_cache (key, payload, updated_at) "
                "VALUES (?, ?, ?)",
                (key, json.dumps(payload, ensure_ascii=False), datetime.now().strftime(_DT_FMT)),
            )
    except Exception:  # noqa: BLE001 — кеш не критичен
        pass


async def _fetch_marker(name: str, zim: str, base: str) -> dict[str, Any] | None:
    try:
        hits = await asyncio.wait_for(
            kiwix.search(name, zim, page_length=3), timeout=LOOKUP_TIMEOUT
        )
    except Exception:  # noqa: BLE001 — справка опциональна
        return None
    if not hits:
        return None
    top = hits[0]
    href = top.get("href") or ""
    article = ""
    if href:
        try:
            article = await asyncio.wait_for(
                kiwix.get_article(zim, href), timeout=LOOKUP_TIMEOUT
            )
        except Exception:  # noqa: BLE001
            article = ""
    text = " ".join(((top.get("snippet") or "") + " " + article).split())
    if not text:
        return None
    return {
        "hit": True,
        "marker": name,
        "title": top.get("title") or name,
        "url": f"{base}/viewer#content/{zim}{href}" if href else "",
        "snippet": text[:CACHE_SNIPPET_MAX],
    }


async def lookup_marker(name: str, zim: str) -> dict[str, Any] | None:
    """Возвращает справку по показателю или None.

    Результат кешируется, включая отрицательный («не найдено»), чтобы не
    повторять один и тот же поиск. Любые сбои возвращают None.
    """
    name = " ".join(str(name or "").split())
    if not name or not zim:
        return None
    base = kiwix.get_base_url()
    if not base:
        return None
    key = f"{zim}|{name.lower()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached if cached.get("hit") else None
    result = await _fetch_marker(name, zim, base)
    _cache_put(key, result if result else {"hit": False})
    return result
