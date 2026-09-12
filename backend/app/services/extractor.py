# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
import json
import logging
import re
from typing import Any

from app.services import i18n, llm, marker_catalog

log = logging.getLogger("extractor")

# Если название показателя не нашлось в каталоге (новый/непонятный маркер),
# приложение ищет о нём справку в офлайн-Википедии (Kiwix) и уточняет разбор.
UNKNOWN_LOOKUP_CAP = 4          # максимум уточняемых показателей за раз
SNIPPET_BUDGET = 800            # символов справки на показатель
GROUNDING_MAX_CHARS = 6000      # общий бюджет справки в промпте
GROUNDING_TIMEOUT = 20.0        # общий лимит времени на поиск справки, сек


def _extract_json(raw: str) -> dict[str, Any]:
    """Вытаскивает первый валидный JSON-объект из ответа LLM."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for start in (m.start() for m in re.finditer(r"\{", text)):
        depth = 0
        closed = False
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    closed = True
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        # Обрыв ответа: скобки не закрылись — пробуем дополнить закрывающими.
        if not closed and depth > 0:
            candidate = text[start:]
            for extra in range(depth, depth + 16):
                try:
                    return json.loads(candidate + "}" * extra)
                except json.JSONDecodeError:
                    pass
    raise ValueError(i18n.t("extract.bad_json"))


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    markers = data.get("markers", [])
    if not isinstance(markers, list):
        markers = []
    markers = [m for m in markers if isinstance(m, dict) and m.get("name")]
    return {
        "date": data.get("date") or None,
        "markers": markers,
        "summary": str(data.get("summary", "") or ""),
    }


def _unknown_marker_names(markers: list[dict[str, Any]]) -> list[str]:
    """Имена показателей, которых нет в каталоге (новые/непонятные/искажённые)."""
    unknown: list[str] = []
    seen: set[str] = set()
    for m in markers:
        name = " ".join(str(m.get("name", "") or "").split())
        if not name:
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        if marker_catalog.canonical_key(name) is None:
            unknown.append(name)
    return unknown


async def _grounding_snippets(
    names: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Ищет справку по показателям в офлайн-Википедии (Kiwix).

    Возвращает (блоки текста «показатель → статья», источники для UI).
    Любые сбои (нет Kiwix, нет сети/таймаут, ничего не найдено) приводят к
    пустым спискам — вызывающий код тогда пропускает уточнение и оставляет
    исходный разбор.
    """
    from app.services import kiwix, wiki_lookup

    empty: tuple[list[str], list[dict[str, Any]]] = ([], [])
    base = kiwix.get_base_url()
    if not base:
        return empty
    try:
        zim = await kiwix.resolve_zim()
    except Exception:  # noqa: BLE001 — справка не должна ломать разбор анализов
        log.info("Kiwix недоступен — уточнение новых показателей пропущено")
        return empty
    if not zim:
        return empty

    blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    for name in names[:UNKNOWN_LOOKUP_CAP]:
        try:
            info = await wiki_lookup.lookup_marker(name, zim)
            if not info:
                continue
            blocks.append(
                f"[{name}] {info['title']}: {info['snippet'][:SNIPPET_BUDGET]}"
            )
            sources.append(
                {
                    "marker": name,
                    "title": info["title"],
                    "url": info.get("url", ""),
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return blocks, sources


def _merge_refined(original: dict[str, Any], refined: dict[str, Any]) -> dict[str, Any]:
    """Возвращает результат уточнения, аккуратно подставляя поля оригинала."""
    markers = refined.get("markers") or original.get("markers") or []
    return {
        "date": refined.get("date") or original.get("date"),
        "markers": markers,
        "summary": refined.get("summary") or original.get("summary") or "",
    }


async def _grounded_refine(data: dict[str, Any]) -> dict[str, Any]:
    """Уточняет разбор через Википедию, если встретились незнакомые показатели."""
    unknown = _unknown_marker_names(data.get("markers", []))
    if not unknown:
        return data

    try:
        snippets, sources = await asyncio.wait_for(
            _grounding_snippets(unknown), timeout=GROUNDING_TIMEOUT
        )
    except Exception:  # noqa: BLE001 — в т.ч. таймаут: уточнение опционально
        return data
    if not snippets:
        return data

    markers_json = json.dumps(
        data.get("markers", []), ensure_ascii=False
    )[:4000]
    snippets_text = "\n\n".join(snippets)[:GROUNDING_MAX_CHARS]
    prompt = i18n.t("extraction_grounded_prompt").format(
        markers_json=markers_json, snippets=snippets_text
    )
    try:
        raw = await llm.complete([{"role": "user", "content": prompt}])
        result = _merge_refined(data, _normalize(_extract_json(raw)))
        result["wiki_sources"] = sources
        return result
    except Exception as exc:  # noqa: BLE001 — уточнение опционально
        log.info("Уточнение через Википедию не удалось (%s); оставлен исходный разбор", exc)
        return data


async def extract_markers(text: str) -> dict[str, Any]:
    """Извлекает маркеры. При неудачном парсинге делает одну повторную
    попытку со строгим промптом (модель иногда обрывает JSON).

    Если среди показателей есть незнакомые каталогу имена, выполняется
    дополнительный проход: поиск справки в офлайн-Википедии (Kiwix)
    и уточнение разбора моделью."""
    last_error: ValueError | None = None
    data: dict[str, Any] | None = None
    catalog = marker_catalog.prompt_hint(i18n.get_lang())
    for key in ("extraction_prompt", "extraction_retry_prompt"):
        try:
            prompt = i18n.t(key).format(text=text[:8000], catalog=catalog)
            raw = await llm.complete([{"role": "user", "content": prompt}])
            data = _normalize(_extract_json(raw))
            break
        except ValueError as exc:
            last_error = exc
            continue
    if data is None:
        raise last_error or ValueError(i18n.t("extract.bad_json"))
    if not data.get("markers"):
        return data
    unknown = _unknown_marker_names(data["markers"])
    if unknown:
        log.info(
            "Распознавание: %d показатель(ей) вне каталога: %s",
            len(unknown),
            ", ".join(unknown[:5]),
        )
    return await _grounded_refine(data)
