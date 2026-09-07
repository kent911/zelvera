# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json
import re
from typing import Any

from app.services import i18n, llm



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


async def extract_markers(text: str) -> dict[str, Any]:
    """Извлекает маркеры. При неудачном парсинге делает одну повторную
    попытку со строгим промптом (модель иногда обрывает JSON)."""
    last_error: ValueError | None = None
    for key in ("extraction_prompt", "extraction_retry_prompt"):
        try:
            prompt = i18n.t(key).format(text=text[:8000])
            raw = await llm.complete([{"role": "user", "content": prompt}])
            return _normalize(_extract_json(raw))
        except ValueError as exc:
            last_error = exc
            continue
    raise last_error or ValueError(i18n.t("extract.bad_json"))
