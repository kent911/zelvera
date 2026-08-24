# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Проверка правдоподобности значений лабораторных показателей.

Ловит явные ошибки OCR/ввода (например, гемоглобин 1450 вместо 145):
значение вне правдоподобных границ помечается как «похоже на ошибку ввода»
и исключается из критичности и трендов.
"""
from typing import Any

from app.services import critical, i18n

# name (нормализованный) -> список границ {unit, min, max}
# min/max — широкие «санитарные» границы (заведомо несовместимы с жизнью/бланком).
PLAUSIBLE_RULES: dict[str, list[dict[str, Any]]] = {
    "гемоглобин": [
        {"unit": "г/л", "min": 30, "max": 300},
        {"unit": "г/дл", "min": 3, "max": 30},
    ],
    "лейкоциты": [
        {"unit": "х10⁹/л", "min": 0.1, "max": 150},
        {"unit": "x10⁹/л", "min": 0.1, "max": 150},
        {"unit": "10⁹/л", "min": 0.1, "max": 150},
        {"unit": "109/л", "min": 0.1, "max": 150},
        {"unit": "тыс/мкл", "min": 0.1, "max": 150},
    ],
    "тромбоциты": [
        {"unit": "х10⁹/л", "min": 5, "max": 2000},
        {"unit": "x10⁹/л", "min": 5, "max": 2000},
        {"unit": "10⁹/л", "min": 5, "max": 2000},
        {"unit": "109/л", "min": 5, "max": 2000},
        {"unit": "тыс/мкл", "min": 5, "max": 2000},
    ],
    "глюкоза": [
        {"unit": "ммоль/л", "min": 0.5, "max": 50},
        {"unit": "мг/дл", "min": 10, "max": 900},
    ],
    "сахар": [
        {"unit": "ммоль/л", "min": 0.5, "max": 50},
        {"unit": "мг/дл", "min": 10, "max": 900},
    ],
    "натрий": [
        {"unit": "ммоль/л", "min": 100, "max": 180},
        {"unit": "мэкв/л", "min": 100, "max": 180},
    ],
    "калий": [
        {"unit": "ммоль/л", "min": 1.5, "max": 9},
        {"unit": "мэкв/л", "min": 1.5, "max": 9},
    ],
    "кальций": [
        {"unit": "ммоль/л", "min": 0.5, "max": 5},
        {"unit": "мг/дл", "min": 2, "max": 20},
    ],
    "креатинин": [
        {"unit": "мкмоль/л", "min": 10, "max": 1500},
        {"unit": "мг/дл", "min": 0.1, "max": 20},
    ],
    "алат": [
        {"unit": "ед/л", "min": 1, "max": 5000},
        {"unit": "u/l", "min": 1, "max": 5000},
    ],
    "алт": [
        {"unit": "ед/л", "min": 1, "max": 5000},
        {"unit": "u/l", "min": 1, "max": 5000},
    ],
    "асat": [
        {"unit": "ед/л", "min": 1, "max": 5000},
        {"unit": "u/l", "min": 1, "max": 5000},
    ],
    "аст": [
        {"unit": "ед/л", "min": 1, "max": 5000},
        {"unit": "u/l", "min": 1, "max": 5000},
    ],
    "мно": [
        {"unit": "", "min": 0.5, "max": 15},
    ],
    "креатининкиназа": [
        {"unit": "ед/л", "min": 5, "max": 100000},
        {"unit": "u/l", "min": 5, "max": 100000},
    ],
    "кк": [
        {"unit": "ед/л", "min": 5, "max": 100000},
        {"unit": "u/l", "min": 5, "max": 100000},
    ],
    "тропонин": [
        {"unit": "нг/мл", "min": 0, "max": 1000},
        {"unit": "нг/л", "min": 0, "max": 100000},
    ],
    "билирубин": [
        {"unit": "мкмоль/л", "min": 1, "max": 1000},
        {"unit": "мг/дл", "min": 0.05, "max": 60},
    ],
    "мочевина": [
        {"unit": "ммоль/л", "min": 0.5, "max": 100},
        {"unit": "мг/дл", "min": 1, "max": 500},
    ],
}

OUT_OF_RANGE = "out_of_range"


def check_plausible(name: str, value: Any, unit: str = "") -> dict[str, Any] | None:
    """Возвращает описание неправдоподобного значения или None.

    Результат: {"code": "out_of_range", "min": <число>, "max": <число>, "unit": <норм. единица>}.
    """
    try:
        val = float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None

    key = critical.SYNONYMS.get(critical._norm(name))
    rules = PLAUSIBLE_RULES.get(key) if key else None
    if not rules:
        return None

    u = critical._clean_unit(unit)
    for rule in rules:
        rule_unit = critical._clean_unit(rule.get("unit", ""))
        if u and rule_unit and u != rule_unit:
            continue
        if rule.get("min") is not None and val < rule["min"]:
            return {
                "code": OUT_OF_RANGE,
                "min": rule["min"],
                "max": rule.get("max"),
                "unit": rule.get("unit", ""),
            }
        if rule.get("max") is not None and val > rule["max"]:
            return {
                "code": OUT_OF_RANGE,
                "min": rule.get("min"),
                "max": rule["max"],
                "unit": rule.get("unit", ""),
            }
    return None


def annotate_markers(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Добавляет каждому маркеру поле validation (None — значение правдоподобно)."""
    out: list[dict[str, Any]] = []
    for m in markers:
        m = dict(m)
        m["validation"] = check_plausible(
            m.get("name"), m.get("value"), m.get("unit", "")
        )
        out.append(m)
    return out


def enrich_markers(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Готовит маркеры для отображения: неправдоподобные значения не считаются
    критическими и получают локализованное предупреждение validation_message."""
    out: list[dict[str, Any]] = []
    for m in markers:
        m = dict(m)
        vcode = m.get("validation")
        if vcode:
            m["critical"] = None
            info = check_plausible(
                m.get("name"), m.get("value"), m.get("unit", "")
            ) or {}
            value = m.get("value_raw") or m.get("value") or "?"
            m["validation_message"] = i18n.t(
                "marker.suspect",
                name=m.get("name") or "",
                value=value,
                unit=m.get("unit") or "",
                min=info.get("min") or "",
                max=info.get("max") or "",
            )
        else:
            m["validation_message"] = None
        out.append(m)
    return out
