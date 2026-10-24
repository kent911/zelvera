# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Клиент kiwix-serve: поиск по офлайн-Википедии (ZIM) и извлечение текста статей.

Документация kiwix-serve (https://kiwix-tools.readthedocs.io):
  - полнотекстовый поиск: GET /search?pattern=<q>&books.name=<zim>&format=xml&pageLength=N
    Ответ — RSS: <rss><channel><item><title>/<link>/<description>.
    <link> содержит absolutePath вида /content/<zimname>/<path>.
    Фильтры без точного имени: books.filter.category=wikipedia, books.filter.lang=eng.
  - сырой контент:       GET /raw/<zim>/content/<path>
  - каталог книг (OPDS): GET /catalog/v2/entries?count=N
Изображения статей лежат в namespace I/ (src вида /I/<имя>). Их описание
делает vision-модель (llm.describe_image); найденные изображения
накапливаются в _pending_images и отправляются на фронтенд через
take_pending_images() после вызова инструмента.
"""
import asyncio
import base64
import hashlib
import html
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import KIWIX_CACHE_DIR
from app.services import settings_store

log = logging.getLogger("kiwix")

TIMEOUT = 15.0
ARTICLE_MAX_CHARS = 4000
ARTICLE_HTML_MAX_CHARS = 300_000
IMAGE_CAP_TOTAL = 8
IMAGE_CAP_PER_ARTICLE = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIN_IMAGE_WIDTH = 100

_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

KIWIX_CACHE_MAX_BYTES = 256 * 1024 * 1024

_cache_dir = Path(KIWIX_CACHE_DIR)


def _cache_key(zim: str, path: str) -> str:
    return hashlib.sha256(f"{zim}\n{path}".encode("utf-8")).hexdigest()


def _cache_bin_path(zim: str, path: str) -> Path:
    return _cache_dir / (_cache_key(zim, path) + ".bin")


def cache_get_sync(zim: str, path: str) -> tuple[bytes | None, str | None]:
    """Читает файл из дискового кеша; возвращает (байты, mime)."""
    bin_path = _cache_bin_path(zim, path)
    try:
        data = bin_path.read_bytes()
    except OSError:
        return None, None
    try:
        mime = _cache_mime_path(zim, path).read_text("utf-8").strip() or None
    except OSError:
        mime = None
    return data, mime


def cache_put_sync(zim: str, path: str, data: bytes, mime: str = "") -> None:
    """Кладёт файл в дисковый кеш и при переполнении чистит старые."""
    try:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        bin_path = _cache_bin_path(zim, path)
        tmp = bin_path.with_suffix(".bin.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, bin_path)
        _cache_mime_path(zim, path).write_text(mime or "", encoding="utf-8")
    except OSError:
        log.debug("kiwix cache: не удалось записать %s %s", zim, path)
        return
    _cache_evict_sync()


def _cache_mime_path(zim: str, path: str) -> Path:
    return _cache_dir / (_cache_key(zim, path) + ".mime")


def _cache_evict_sync() -> None:
    try:
        files = sorted(_cache_dir.glob("*.bin"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    total = sum(p.stat().st_size for p in files)
    while files and total > KIWIX_CACHE_MAX_BYTES:
        old = files.pop(0)
        try:
            total -= old.stat().st_size
            old.unlink()
            old.with_suffix(".mime").unlink(missing_ok=True)
        except OSError:
            continue


async def cache_get(zim: str, path: str) -> tuple[bytes | None, str | None]:
    return await asyncio.to_thread(cache_get_sync, zim, path)


async def cache_put(zim: str, path: str, data: bytes, mime: str = "") -> None:
    await asyncio.to_thread(cache_put_sync, zim, path, data, mime)

_pending_images: list[dict] = []


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


_CONNECTION_CACHE: dict[str, Any] = {}
_CONNECTION_TTL = 30.0


async def check_connection() -> dict[str, Any]:
    """Проверяет доступность kiwix-serve (с коротким TTL-кешем)."""
    now = time.monotonic()
    cached = _CONNECTION_CACHE.get("value")
    if cached is not None and now - _CONNECTION_CACHE.get("ts", 0) < _CONNECTION_TTL:
        return cached
    base = get_base_url()
    zim = get_zim_name()
    if not base:
        result = {"ok": False, "url": "", "zim": zim, "error": "kiwix.no_url"}
    else:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{base}/catalog/v2/entries?count=1")
                resp.raise_for_status()
            result = {"ok": True, "url": base, "zim": zim, "error": ""}
        except httpx.HTTPError as exc:
            result = {"ok": False, "url": base, "zim": zim, "error": str(exc)}
    _CONNECTION_CACHE["ts"] = now
    _CONNECTION_CACHE["value"] = result
    return result


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


async def get_article_html(zim: str, path: str, max_chars: int = ARTICLE_HTML_MAX_CHARS) -> str:
    """Возвращает сырой HTML статьи (ограничен), для извлечения <img> и текста."""
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
                return resp.text[:max_chars]
        except httpx.HTTPError as exc:
            errors.append(str(exc))
    raise KiwixError("kiwix.article_failed", err="; ".join(errors))


def _normalize_img_src(src: str, article_zim: str, article_path: str = "/") -> tuple[str, str]:
    """Приводит src картинки к (zim, /path). Пусто, если путь непригоден.

    Форматы src в сыром HTML ZIM:
      - ./_assets_/Файл  (новые ZIM: ассеты рядом со статьёй в namespace A)
      - ../I/Файл        (старые ZIM: статьи в A/, картинки в I/)
      - /I/Файл, /<zim>/I/Файл, /content/<zim>/I/Файл
    Имена могут быть процентно-закодированы (в т.ч. дважды, %252B).
    """
    import posixpath
    from urllib.parse import unquote

    src = src.split("#")[0].split("?")[0].strip()
    if not src:
        return "", ""
    if "/content/" in src:
        zim, path = _split_content_link(src)
        return (zim or article_zim), unquote(path)
    if src.startswith("/I/"):
        return article_zim, unquote(src)
    if src.startswith("/"):
        rest = src.lstrip("/")
        parts = rest.split("/", 1)
        if len(parts) == 2 and parts[0] == article_zim and parts[1].startswith("I/"):
            return article_zim, "/" + unquote(parts[1])
        return "", ""
    base = posixpath.dirname(article_path or "/")
    joined = posixpath.normpath(posixpath.join(base, unquote(src)))
    if joined.startswith("/I/") or "/_assets_/" in joined:
        return article_zim, joined
    return "", ""


_IMG_TAG_RE = re.compile(r"<img[^>]*>", flags=re.I)


def _extract_images(
    raw: str, article_zim: str, article_path: str, max_images: int
) -> list[dict[str, str]]:
    """Извлекает <img ... src=...> из HTML статьи в порядке появления.

    Ведущая/инфобокс-картинка обычно стоит первой в статье (часто без alt),
    поэтому порядок документа сохраняется; отсекаются только мелкие иконки.
    """
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tag in _IMG_TAG_RE.findall(raw):
        src_m = re.search(
            r"\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", tag, flags=re.I
        )
        if not src_m:
            continue
        src = src_m.group(1) if src_m.group(1) is not None else src_m.group(2)
        zim, path = _normalize_img_src(src or "", article_zim, article_path)
        if not zim or not path:
            continue
        width_m = re.search(r'\bwidth\s*=\s*"(\d+)"', tag, flags=re.I)
        if width_m and int(width_m.group(1)) < MIN_IMAGE_WIDTH:
            continue
        key = (zim, path)
        if key in seen:
            continue
        seen.add(key)
        alt_m = re.search(r"\balt\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", tag, flags=re.I)
        alt = ""
        if alt_m:
            alt = (alt_m.group(1) if alt_m.group(1) is not None else alt_m.group(2) or "")
            alt = html.unescape(alt).strip()
        candidates.append({"zim": zim, "path": path, "alt": alt})
    return candidates[: max(0, int(max_images))]


def take_pending_images() -> list[dict]:
    """Забирает накопленные инструментом изображения и очищает очередь."""
    global _pending_images
    imgs = _pending_images
    _pending_images = []
    return imgs


def _record_image(
    zim: str,
    path: str,
    caption: str,
    source: str = "",
    index: int | None = None,
) -> None:
    if not zim or not path:
        return
    url = f"/api/kiwix/image?zim={quote(zim, safe='')}&path={quote(path, safe='/')}"
    item = {"zim": zim, "path": path, "caption": caption, "url": url, "source": source}
    if index is not None:
        item["index"] = index
    if item not in _pending_images:
        _pending_images.append(item)


def _mime_for_path(path: str) -> str:
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return _MIME_BY_EXT.get("." + ext.lower(), "image/jpeg")


def _image_url_candidates(zim: str, path: str) -> list[tuple[str, str]]:
    """Кандидаты (рабочий_путь, url) для загрузки изображения.

    В разных ZIM один и тот же файл лежит в A/_assets_/, I/_assets_/ или I/.
    """
    base = get_base_url()
    if not base:
        return []
    variants: list[str] = [path]
    name: str | None = None
    if "/_assets_/" in path:
        name = path.rsplit("/_assets_/", 1)[-1]
    elif path.startswith("/I/"):
        name = path[len("/I/"):]
    if name:
        if path.startswith("/A/_assets_/"):
            variants += ["/I/_assets_/" + name, "/I/" + name]
        elif path.startswith("/I/_assets_/"):
            variants += ["/A/_assets_/" + name, "/I/" + name]
        elif path.startswith("/I/"):
            variants += ["/I/_assets_/" + name, "/A/_assets_/" + name]
    return [
        (v, f"{base}/raw/{quote(zim, safe='')}/content{quote(v, safe='/')}")
        for v in variants
    ]


async def _fetch_image(zim: str, path: str) -> tuple[bytes | None, str]:
    """Загружает изображение; возвращает (байты, рабочий_путь) или (None, "").

    Сначала проверяет дисковый кеш — повторные загрузки (та же статья в чате,
    повторные вопросы) не ходят в Kiwix.
    """
    for variant, url in _image_url_candidates(zim, path):
        cached, _ = await cache_get(zim, variant)
        if cached is not None:
            if len(cached) <= MAX_IMAGE_BYTES:
                return cached, variant
            continue
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content
                if len(data) <= MAX_IMAGE_BYTES:
                    await cache_put(
                        zim, variant, data, resp.headers.get("Content-Type", "")
                    )
                    return data, variant
        except httpx.HTTPError:
            continue
    return None, ""


def _normalize_image_for_vision(img_bytes: bytes, fallback_mime: str) -> tuple[bytes, str]:
    """Перекодирует изображение в JPEG (RGB, макс. 1024px) для vision-модели.

    Часть ассетов ZIM — файлы вида *.svg.png большого размера или в
    формате, который Ollama не декодирует. Pillow нормализует картинку.
    При неудаче возвращает оригинал.
    """
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(img_bytes)) as img:
            img.load()
            img = img.convert("RGB")
            w, h = img.size
            max_dim = 1024
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=88)
            return buf.getvalue(), "image/jpeg"
    except Exception:
        return img_bytes, fallback_mime


async def _describe_image_bytes(img_bytes: bytes, fallback_mime: str) -> str | None:
    """Описание картинки vision-моделью; None — модель недоступна/не поддерживает."""
    from app.services.llm import LLMError, describe_image

    norm_bytes, norm_mime = _normalize_image_for_vision(img_bytes, fallback_mime)
    try:
        desc = await describe_image(
            base64.b64encode(norm_bytes).decode("ascii"), norm_mime
        )
    except LLMError as exc:
        log.warning(
            "kiwix: vision-описание недоступно: %s (байт: %d, mime: %s)",
            exc,
            len(img_bytes),
            fallback_mime,
        )
        return None
    return (desc or "").strip()


async def fetch_tool_results(query: str, limit: int = 3) -> str:
    """Готовит ответ для инструмента ИИ: сниппеты поиска + тексты статей.

    Также извлекает картинки из статей (namespace I/), описывает их
    vision-моделью и накапливает в _pending_images для показа в чате.
    """
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
    image_count = 0
    image_legend: list[str] = []
    vision_available = True
    for item in results[: max(1, min(int(limit), 5))]:
        header = f"[Wikipedia: {item['title'] or item['href']}]"
        body_parts = []
        if item.get("snippet"):
            body_parts.append(item["snippet"])
        if item.get("href"):
            article_zim = item.get("zim") or zim
            if article_zim:
                html_text = ""
                try:
                    html_text = await get_article_html(article_zim, item["href"])
                except (KiwixError, httpx.HTTPError):
                    pass
                if html_text:
                    article = _strip_html(html_text)[:ARTICLE_MAX_CHARS]
                    if article:
                        body_parts.append(article)
                    if image_count < IMAGE_CAP_TOTAL:
                        images_for_article = _extract_images(
                            html_text, article_zim, item["href"], IMAGE_CAP_PER_ARTICLE
                        )
                        if not images_for_article:
                            img_tags = _IMG_TAG_RE.findall(html_text)
                            if img_tags:
                                log.info(
                                    "kiwix: статья %s: %d <img>, но не извлечено ни одного; примеры src: %s",
                                    item["href"],
                                    len(img_tags),
                                    "; ".join(img_tags[:3])[:400],
                                )
                        for img in images_for_article:
                            if image_count >= IMAGE_CAP_TOTAL:
                                break
                            data, working_path = await _fetch_image(img["zim"], img["path"])
                            if data is None:
                                continue
                            caption = img["alt"]
                            if vision_available:
                                desc = await _describe_image_bytes(
                                    data, _mime_for_path(working_path)
                                )
                                if desc is None:
                                    vision_available = False
                                elif desc:
                                    caption = desc
                            image_count += 1
                            title = item.get("title") or item.get("href") or ""
                            _record_image(
                                img["zim"],
                                working_path,
                                caption,
                                source=title,
                                index=image_count,
                            )
                            tag = f"[Image {image_count}: {caption}]" if caption else f"[Image {image_count}]"
                            body_parts.append(tag)
                            image_legend.append(
                                f"{image_count}. {caption or 'image'} (Wikipedia: {title})"
                            )
        if body_parts:
            blocks.append(header + "\n" + "\n".join(body_parts))
    if image_count:
        log.info("kiwix: по запросу %r извлечено изображений: %d", query, image_count)
        blocks.append(
            "Available images — after the paragraph each picture illustrates, "
            "output [[рис. N]] on its own line. Do not dump images at the end.\n"
            + "\n".join(image_legend)
        )
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
