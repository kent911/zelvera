# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Клиент kiwix-serve: поиск по офлайн-Википедии (ZIM) и извлечение текста статей.

Документация kiwix-serve (https://kiwix-tools.readthedocs.io):
  - полнотекстовый поиск: GET /search?pattern=<q>&books.name=<zim>&format=xml&pageLength=N
    Ответ — RSS: <rss><channel><item><title>/<link>/<description>.
    <link> содержит absolutePath вида /content/<zimname>/<path>.
    Фильтры без точного имени: books.filter.category=wikipedia, books.filter.lang=eng.
  - сырой контент:       GET /raw/<zim>/content/<path>
  - каталог книг (OPDS): GET /catalog/v2/entries?count=N
"""
import html
import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

from app.services import settings_store

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


def _split_content_link(href: str) -> tuple[str, str]:
    """Разбирает /content/<zim>/<path> на (zim, /path). Иначе (None, href)."""
    href = href.split("#")[0].split("?")[0]
    if "/content/" in href:
        rest = href.split("/content/")[-1]
        parts = rest.split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], "/" + parts[1]
        return parts[0] if parts else None, ""
    if not href.startswith("/"):
        href = "/" + href
    return None, href


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


def _parse_books_info_xml(raw: str) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    books: list[dict[str, str]] = []

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    for entry in root.iter():
        if local(entry.tag) != "entry":
            continue
        info: dict[str, str] = {"name": "", "title": "", "language": "", "category": ""}
        for child in entry:
            tag = local(child.tag)
            value = (child.text or "").strip()
            if tag in info and value:
                info[tag] = value
        if info["name"]:
            books.append(info)
    return books


async def get_books_info() -> list[dict[str, str]]:
    """Список подключённых книг с метаданными: name, title, language, category."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")
    errors: list[str] = []
    try:
        data = await _get_json(base, "/catalog/v2/entries?count=200")
        if data is not None:
            entries = (
                data.get("data", {}).get("entries", []) if isinstance(data.get("data"), dict) else []
            )
            if not entries and isinstance(data.get("data"), list):
                entries = data["data"]
            books: list[dict[str, str]] = []
            for e in entries:
                if not isinstance(e, dict):
                    continue
                meta = e.get("metadata") if isinstance(e.get("metadata"), dict) else e
                lang = meta.get("language")
                if isinstance(lang, list):
                    lang = ", ".join(str(x) for x in lang)
                info = {
                    "name": str(meta.get("name") or meta.get("identifier") or ""),
                    "title": str(meta.get("title") or ""),
                    "language": str(lang or ""),
                    "category": str(meta.get("category") or ""),
                }
                if info["name"]:
                    books.append(info)
            if books:
                return books
            errors.append("JSON: no entries")
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    try:
        url = f"{base}/catalog/v2/entries?count=200"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _parse_books_info_xml(resp.text)
    except (httpx.HTTPError, ET.ParseError) as exc:
        errors.append(str(exc))
    raise KiwixError("kiwix.books_failed", err="; ".join(errors))


async def get_books() -> list[str]:
    """Имена ZIM-книг, доступных в kiwix-serve."""
    books = await get_books_info()
    return [b["name"] for b in books if b["name"]]


def _pick_wikipedia_zim(names: list[str]) -> str | None:
    candidates = [n for n in names if "wikipedia" in n.lower()]
    en = [n for n in candidates if "_en_" in n or "en" in n.lower().split("_")]
    pool = en or candidates
    meta = [n for n in pool if "meta" in n.lower()]
    for n in meta:
        pool.remove(n)
    return pool[0] if pool else None


async def resolve_zim() -> str:
    """Точное имя ZIM-книги: из настроек, иначе автоопределение. Может вернуть ""."""
    name = get_zim_name()
    if name:
        return name
    try:
        books = await get_books()
        picked = _pick_wikipedia_zim(books)
        if picked:
            return picked
    except KiwixError:
        pass
    return ""


def _parse_search_xml(text: str) -> list[dict[str, str]]:
    """Разбирает RSS-ответ /search: item → title / link(absolutePath) / description."""
    results: list[dict[str, str]] = []

    def make_item(title: str, link_text: str, snippet: str) -> dict[str, str]:
        zim, path = _split_content_link(link_text)
        return {
            "title": _strip_html(title),
            "href": path,
            "snippet": _strip_html(snippet),
            "zim": zim or "",
        }

    try:
        root = ET.fromstring(text)
        for item in root.findall(".//item"):
            link_el = item.find("link")
            link_text = (link_el.text or "").strip() if link_el is not None else ""
            desc_el = item.find("description")
            desc_text = "".join(desc_el.itertext()) if desc_el is not None else ""
            results.append(
                make_item(
                    item.findtext("title", "") or "",
                    link_text,
                    desc_text,
                )
            )
    except ET.ParseError:
        for block in re.findall(r"<item[^>]*>(.*?)</item>", text, flags=re.S):
            def grab(tag: str) -> str:
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, flags=re.S)
                return m.group(1) if m else ""

            results.append(make_item(grab("title"), grab("link").strip(), grab("description")))

    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for r in results:
        key = r["href"] or r["title"]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(r)
    return cleaned


async def search(query: str, zim: str, page_length: int = 20) -> list[dict[str, str]]:
    """Полнотекстовый поиск. При неверном имени книги — fallback на фильтры."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")

    def url_for(book_query: str) -> str:
        return (
            f"{base}/search?pattern={quote(query)}&{book_query}"
            f"&format=xml&pageLength={int(page_length)}"
        )

    filter_q = "books.filter.category=wikipedia&books.filter.lang=eng"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if zim:
            resp = await client.get(url_for(f"books.name={quote(zim)}"))
            if resp.status_code == 400:
                resp = await client.get(url_for(filter_q))
        else:
            resp = await client.get(url_for(filter_q))
        resp.raise_for_status()
        text = resp.text
    results = _parse_search_xml(text)
    if zim:
        for r in results:
            r.setdefault("zim", zim)
    return results


async def get_article(zim: str, path: str) -> str:
    """Возвращает текст статьи без HTML, ограниченный ARTICLE_MAX_CHARS."""
    base = get_base_url()
    if not base:
        raise KiwixError("kiwix.not_configured")
    attempts = [
        f"{base}/raw/{zim}/content{path}",
        f"{base}/raw/{zim}{path}",
    ]
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
            article_zim = item.get("zim") or zim
            if article_zim:
                try:
                    article = await get_article(article_zim, item["href"])
                    if article:
                        body_parts.append(article)
                except (KiwixError, httpx.HTTPError):
                    pass
        if body_parts:
            blocks.append(header + "\n" + "\n".join(body_parts))
    if not blocks:
        return t("kiwix.no_results")
    return "\n\n---\n\n".join(blocks)


async def fetch_books_tool_result() -> str:
    """Ответ для инструмента ИИ list_kiwix_books: подключённые книги."""
    from app.services.i18n import t

    try:
        books = await get_books_info()
    except KiwixError as exc:
        detail = t(exc.key)
        if exc.err:
            detail = f"{detail} ({exc.err})"
        return f"{t('error.prefix')} {detail}"
    except httpx.HTTPError as exc:
        return f"{t('error.prefix')} {t('kiwix.unreachable', url=get_base_url() or '—', err=exc)}"
    if not books:
        return t("kiwix.no_books")
    lines: list[str] = []
    for b in books:
        label = f"{b['title'] or b['name']} ({b['name']})"
        if b.get("language"):
            label += f" — {b['language']}"
        lines.append(f"• {label}")
    return "\n".join(lines)
