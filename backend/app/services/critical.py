# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Критические отклонения лабораторных показателей.

Определяет опасные для жизни значения по базе порогов. Используется для
подсветки в мед. карте и для предупреждения в чате.
"""
from typing import Any


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


# name (нормализованный) -> список порогов {unit, low, high}
# low/high — критические границы (включительно снаружи).
CRITICAL_RULES: dict[str, list[dict[str, Any]]] = {
    "гемоглобин": [
        {"unit": "г/л", "low": 70, "high": 200},
        {"unit": "г/дл", "low": 7.0, "high": 20},
    ],
    "лейкоциты": [
        {"unit": "х10⁹/л", "low": 1.0, "high": 30},
        {"unit": "x10⁹/л", "low": 1.0, "high": 30},
        {"unit": "10⁹/л", "low": 1.0, "high": 30},
        {"unit": "109/л", "low": 1.0, "high": 30},
        {"unit": "тыс/мкл", "low": 1.0, "high": 30},
        {"unit": "г/л", "low": 1.0, "high": 30},
    ],
    "тромбоциты": [
        {"unit": "х10⁹/л", "low": 20, "high": 1000},
        {"unit": "x10⁹/л", "low": 20, "high": 1000},
        {"unit": "10⁹/л", "low": 20, "high": 1000},
        {"unit": "109/л", "low": 20, "high": 1000},
        {"unit": "тыс/мкл", "low": 20, "high": 1000},
    ],
    "глюкоза": [
        {"unit": "ммоль/л", "low": 2.2, "high": 27.8},
        {"unit": "мг/дл", "low": 40, "high": 500},
    ],
    "сахар": [
        {"unit": "ммоль/л", "low": 2.2, "high": 27.8},
        {"unit": "мг/дл", "low": 40, "high": 500},
    ],
    "натрий": [
        {"unit": "ммоль/л", "low": 120, "high": 160},
        {"unit": "мэкв/л", "low": 120, "high": 160},
    ],
    "калий": [
        {"unit": "ммоль/л", "low": 2.5, "high": 6.5},
        {"unit": "мэкв/л", "low": 2.5, "high": 6.5},
    ],
    "кальций": [
        {"unit": "ммоль/л", "low": 1.5, "high": 3.5},
        {"unit": "мг/дл", "low": 6.0, "high": 14.0},
    ],
    "креатинин": [
        {"unit": "мкмоль/л", "high": 500},
        {"unit": "мг/дл", "high": 5.7},
    ],
    "алат": [
        {"unit": "ед/л", "high": 1000},
        {"unit": "u/l", "high": 1000},
    ],
    "алт": [
        {"unit": "ед/л", "high": 1000},
        {"unit": "u/l", "high": 1000},
    ],
    "асat": [
        {"unit": "ед/л", "high": 1000},
        {"unit": "u/l", "high": 1000},
    ],
    "аст": [
        {"unit": "ед/л", "high": 1000},
        {"unit": "u/l", "high": 1000},
    ],
    "мно": [
        {"unit": "", "high": 5.0},
    ],
    "креатининкиназа": [
        {"unit": "ед/л", "high": 20000},
        {"unit": "u/l", "high": 20000},
    ],
    "кк": [
        {"unit": "ед/л", "high": 20000},
        {"unit": "u/l", "high": 20000},
    ],
    "тропонин": [
        {"unit": "нг/мл", "high": 0.1},
        {"unit": "нг/л", "high": 100},
    ],
    "билирубин": [
        {"unit": "мкмоль/л", "high": 400},
        {"unit": "мг/дл", "high": 23.4},
    ],
    "мочевина": [
        {"unit": "ммоль/л", "high": 40},
        {"unit": "мг/дл", "high": 240},
    ],
}

# синонимы нормализованных имён -> канонический ключ
SYNONYMS: dict[str, str] = {
    "гемоглобин": "гемоглобин",
    "hb": "гемоглобин",
    "hgb": "гемоглобин",
    "лейкоциты": "лейкоциты",
    "wbc": "лейкоциты",
    "тромбоциты": "тромбоциты",
    "plt": "тромбоциты",
    "глюкоза": "глюкоза",
    "сахар": "сахар",
    "глюкозаплазмы": "глюкоза",
    "натрий": "натрий",
    "na": "натрий",
    "калий": "калий",
    "k": "калий",
    "кальций": "кальций",
    "ca": "кальций",
    "креатинин": "креатинин",
    "алат": "алат",
    "алт": "алт",
    "аланинаминотрансфераза": "алат",
    "асat": "асat",
    "аст": "аст",
    "аспартатаминотрансфераза": "асat",
    "мно": "мно",
    "inr": "мно",
    "креатининкиназа": "креатининкиназа",
    "кфк": "креатининкиназа",
    "кк": "кк",
    "тропонин": "тропонин",
    "билирубин": "билирубин",
    "мочевина": "мочевина",
}

ALIAS_UNITS = {
    "моль/л": "ммоль/л",
    "мекв/л": "мэкв/л",
    "г/дцл": "г/дл",
    "10^9/л": "х10⁹/л",
    "x10^9/л": "х10⁹/л",
    "ед\л": "ед/л",
}


def _clean_unit(unit: str) -> str:
    u = "".join(ch for ch in (unit or "").lower().strip() if ch.isalnum() or ch in "/·^")
    u = ALIAS_UNITS.get(u, u)
    return u


def check_critical(name: str, value: Any, unit: str = "") -> dict[str, Any] | None:
    """Возвращает описание критического отклонения или None.

    Результат: {"level": "low"|"high", "threshold": <число>, "unit": <норм. единица>}.
    """
    try:
        val = float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None

    key = SYNONYMS.get(_norm(name))
    rules = CRITICAL_RULES.get(key) if key else None
    if not rules:
        return None

    u = _clean_unit(unit)
    for rule in rules:
        rule_unit = _clean_unit(rule["unit"])
        if u and rule_unit and u != rule_unit:
            continue
        if rule.get("low") is not None and val < rule["low"]:
            return {"level": "low", "threshold": rule["low"], "unit": rule["unit"]}
        if rule.get("high") is not None and val > rule["high"]:
            return {"level": "high", "threshold": rule["high"], "unit": rule["unit"]}
    return None


def flag_markers(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Помечает маркеры полем critical (None — не критично)."""
    out: list[dict[str, Any]] = []
    for m in markers:
        crit = check_critical(m.get("name"), m.get("value"), m.get("unit", ""))
        out.append({**m, "critical": crit})
    return out


def critical_warnings(markers: list[dict[str, Any]]) -> list[str]:
    """Формирует текстовые предупреждения для чата."""
    warnings: list[str] = []
    for m in flag_markers(markers):
        crit = m.get("critical")
        if not crit:
            continue
        level = "ниже" if crit["level"] == "low" else "выше"
        warnings.append(
            f"{m.get('name')}: {m.get('value_raw') or m.get('value')} {m.get('unit') or ''} "
            f"({level} критического порога {crit['threshold']} {crit['unit']})"
        )
    return warnings
