# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json
import re
from typing import Any

from app.services import i18n, llm



def _extract_json(raw: str) -> dict[str, Any]:
    """Вытаскивает первый JSON-объект из ответа LLM."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError(i18n.t("extract.no_json"))
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break
    raise ValueError(i18n.t("extract.bad_json"))


async def extract_markers(text: str) -> dict[str, Any]:
    prompt = i18n.t("extraction_prompt").format(text=text[:8000])
    raw = await llm.complete(
        [{"role": "user", "content": prompt}],
    )
    data = _extract_json(raw)

    markers = data.get("markers", [])
    if not isinstance(markers, list):
        markers = []
    markers = [m for m in markers if isinstance(m, dict) and m.get("name")]

    return {
        "date": data.get("date") or None,
        "markers": markers,
        "summary": str(data.get("summary", "") or ""),
    }
