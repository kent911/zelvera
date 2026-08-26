# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Клиент kiwix-serve: поиск по офлайн-Википедии (ZIM) и извлечение текста статей.

Эндпоинты kiwix-serve:
  - полнотекстовый поиск: GET /search?pattern=<q>&books.name=<zim>&format=xml&pageLength=N
  - сырой контент:        GET /raw/<zim>/<path>
  - каталог книг (OPDS):  GET /catalog/v2/entries
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.services import settings_store

ATOM_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/terms/"
TIMEOUT = 15.0
ARTICLE_MAX_CHARS = 4000


class KiwixError(Exception):
    def __init__(self, key: str, err: str = ""):
        super().__init__(key)
        self.key = key
        self.err = err


def _strip_html(raw: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _content_path(href: str) -> str:
    """Преобразует ссылку из результатов поиска в путь внутри ZIM (/A/Статья)."""
    href = href.split("#")[0]
    if "/content/" in href:
        href = href.split("/content/")[-1]
    if not href.startswith("/"):
        href = "/" + href
    return href


def get_base_url() -> str:
    return settings_store.get("kiwix_base_url").strip().rstrip("/") or ""


def get_zim_name() -> str:
    return settings_store.get("kiwix_zim_name").strip()


async def _get_json(base: str, path: str) -> dict[str, Any] | None:
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        text = resp.text.lstrip()
        if text.startswith("{"):
            return json.loads(text)
    return None


def _parse_books_xml(raw: str) -> list[str]:
    root = ET.fromstring(raw)
    names: list[str] = []

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def text_of(elem: ET.Element) -> str:
        return (elem.text or "").strip()

    for entry in root.iter():
        if local(entry.tag) != "entry":
            continue
        for child in entry.iter():
            name = local(child.tag)
            value = text_of(child)
            if not value:
                continue
            if name == "name" and "/entries/" in value:
                continue
            if name == "name":
                names.append(value)
            elif name == "identifier":
                names.append(value)
            elif name == "link":
                href = child.attrib.get("href", "")
                if "/entries/" in href:
                    names.append(href.rsplit("/", 1)[-1])
    return list(dict.fromkeys(n for n in names if n))


async def get_books() -> list[str]:
    """Список имён ZIM-книг, доступных в kiwix-serve."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")
    errors: list[str] = []
    try:
        data = await _get_json(base, "/catalog/v2/entries?count=200")
        if data is not None:
            candidates: list[str] = []
            entries = (
                data.get("data", {}).get("entries", []) if isinstance(data.get("data"), dict) else []
            )
            if not entries and isinstance(data.get("data"), list):
                entries = data["data"]
            for e in entries:
                if isinstance(e, str):
                    candidates.append(e)
                    continue
                if not isinstance(e, dict):
                    continue
                meta = e.get("metadata") if isinstance(e.get("metadata"), dict) else e
                for key in ("name", "identifier"):
                    if meta.get(key):
                        candidates.append(str(meta[key]))
                        break
            names = list(dict.fromkeys(c for c in candidates if c))
            if names:
                return names
            errors.append("JSON: no entries")
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    try:
        url = f"{base}/catalog/v2/entries?count=200"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _parse_books_xml(resp.text)
    except (httpx.HTTPError, ET.ParseError) as exc:
        errors.append(str(exc))
    raise KiwixError("kiwix.books_failed", err="; ".join(errors))


def _pick_wikipedia_zim(names: list[str]) -> str | None:
    candidates = [n for n in names if "wikipedia" in n.lower()]
    en = [n for n in candidates if "_en_" in n or "en" in n.lower().split("_")]
    pool = en or candidates
    meta = [n for n in pool if "meta" in n.lower()]
    for n in meta:
        pool.remove(n)
    return pool[0] if pool else None


async def resolve_zim() -> str:
    name = get_zim_name()
    if name:
        return name
    books = await get_books()
    picked = _pick_wikipedia_zim(books)
    if picked:
        return picked
    raise KiwixError("kiwix.zim_not_found")


async def search(query: str, zim: str, page_length: int = 20) -> list[dict[str, str]]:
    """Полнотекстовый поиск по книге. Возвращает title / href / snippet."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")
    from urllib.parse import quote

    url = (
        f"{base}/search?pattern={quote(query)}&books.name={quote(zim)}"
        f"&format=xml&pageLength={int(page_length)}"
    )
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text
    results: list[dict[str, str]] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = None
    if root is not None:
        ns = {"a": ATOM_NS}
        for entry in root.findall(".//a:entry", ns):
            title = entry.findtext("a:title", "", ns)
            link = entry.find("a:link", ns)
            href = link.attrib.get("href", "") if link is not None else ""
            summary = entry.findtext("a:summary", "", ns)
            results.append(
                {
                    "title": _strip_html(title),
                    "href": href,
                    "snippet": _strip_html(summary),
                }
            )
    else:
        for block in re.findall(r"<entry[^>]*>(.*?)</entry>", text, flags=re.S):
            def grab(tag: str) -> str:
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, flags=re.S)
                return m.group(1) if m else ""

            href = ""
            m = re.search(r'<link[^>]*href="([^"]+)"', block)
            if m:
                href = m.group(1)
            results.append(
                {
                    "title": _strip_html(grab("title")),
                    "href": href,
                    "snippet": _strip_html(grab("summary")),
                }
            )
    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for r in results:
        key = r["href"] or r["title"]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(r)
    return cleaned


async def get_article(zim: str, path: str) -> str:
    """Возвращает текст статьи без HTML, ограниченный ARTICLE_MAX_CHARS."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")
    content_path = _content_path(path)
    attempts = [f"{base}/raw/{zim}{content_path}", f"{base}/raw/{zim}/content{content_path}"]
    errors: list[str] = []
    for url in attempts:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return _strip_html(resp.text)[:ARTICLE_MAX_CHARS]
        except httpx.HTTPError as exc:
            errors.append(str(exc))
    raise KiwixError("kiwix.article_failed", err="; ".join(errors))


async def fetch_tool_results(query: str, limit: int = 3) -> str:
    """Готовит ответ для инструмента ИИ: сниппеты поиска + тексты статей."""
    from app.services.i18n import t

    query = query.strip()
    if not query:
        return t("kiwix.empty_query")
    try:
        zim = await resolve_zim()
        results = await search(query, zim)
    except KiwixError as exc:
        detail = t(exc.key)
        if exc.err:
            detail = f"{detail} ({exc.err})"
        return f"{t('error.prefix')} {detail}"
    except httpx.HTTPError as exc:
        return f"{t('error.prefix')} {t('kiwix.unreachable', url=get_base_url() or '—', err=exc)}"
    if not results:
        return t("kiwix.no_results")
    blocks: list[str] = []
    for item in results[: max(1, min(int(limit), 5))]:
        header = f"[Wikipedia: {item['title'] or item['href']}]"
        body_parts = []
        if item.get("snippet"):
            body_parts.append(item["snippet"])
        if item.get("href"):
            try:
                article = await get_article(zim, item["href"])
                if article:
                    body_parts.append(article)
            except (KiwixError, httpx.HTTPError):
                pass
        if body_parts:
            blocks.append(header + "\n" + "\n".join(body_parts))
    if not blocks:
        return t("kiwix.no_results")
    return "\n\n---\n\n".join(blocks)
