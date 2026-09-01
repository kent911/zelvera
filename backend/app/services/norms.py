# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Справочник референсных норм лабораторных показателей.

Используется инструментом ИИ check_marker_norm: по названию показателя,
значению, единицам, полу и возрасту возвращает ожидаемый референсный
диапазон и статус (в норме / выше / ниже).

Внимание: референсы зависят от лаборатории, метода и возраста. Таблицы —
обобщённые ориентиры для взрослых.
"""
from typing import Any

from app.services import critical

# Сопоставление синонимов имён (наследуем словарь critical + расширяем).
SYNONYMS: dict[str, str] = dict(critical.SYNONYMS)
SYNONYMS.update(
    {
        "холестерин": "холестерин",
        "холестерол": "холестерин",
        "общийхолестерин": "холестерин",
        "лпнп": "лпнп",
        "холестеринлпнп": "лпнп",
        "лпвп": "лпвп",
        "холестеринлпвп": "лпвп",
        "триглицериды": "триглицериды",
        "тг": "триглицериды",
        "гликированныйгемоглобин": "гликированныйгемоглобин",
        "нба1с": "гликированныйгемоглобин",
        "hba1c": "гликированныйгемоглобин",
        "ферритин": "ферритин",
        "среактивныйбелок": "среактивныйбелок",
        "срб": "среактивныйбелок",
        "crp": "среактивныйбелок",
        "витаминд": "витаминд",
        "25ohd": "витаминд",
        "25онвитаминд": "витаминд",
        "ттг": "ттг",
        "тиреотропныйгормон": "ттг",
        "tsh": "ттг",
        "т4свободный": "т4свободный",
        "тироксинсвободный": "т4свободный",
        "свободныйтироксин": "т4свободный",
        "мочеваякислота": "мочеваякислота",
        "альбумин": "альбумин",
        "общийбелок": "общийбелок",
        "амилаза": "амилаза",
        "соэ": "соэ",
        "эсо": "соэ",
        "esr": "соэ",
        "гемоглобин": "гемоглобин",
    }
)

# Правило: {"unit", "min", "max", "sex", "age_min", "age_max", "note"}.
# sex: "m"|"f"; age в годах; note — человекочитаемое пояснение (RU).
NORM_RULES: dict[str, dict[str, Any]] = {
    "гемоглобин": {
        "label": "Гемоглобин",
        "rules": [
            {"unit": "г/л", "min": 110, "max": 150, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "г/л", "min": 130, "max": 170, "sex": "m", "age_min": 13, "note": "взрослые мужчины"},
            {"unit": "г/л", "min": 120, "max": 160, "sex": "f", "age_min": 13, "note": "взрослые женщины"},
            {"unit": "г/дл", "min": 11, "max": 15, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "г/дл", "min": 13, "max": 17, "sex": "m", "age_min": 13, "note": "взрослые мужчины"},
            {"unit": "г/дл", "min": 12, "max": 16, "sex": "f", "age_min": 13, "note": "взрослые женщины"},
        ],
    },
    "лейкоциты": {
        "label": "Лейкоциты (WBC)",
        "rules": [
            {"unit": "х10⁹/л", "min": 4.5, "max": 13.5, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "х10⁹/л", "min": 4.0, "max": 9.0, "age_min": 13, "note": "взрослые"},
            {"unit": "x10⁹/л", "min": 4.5, "max": 13.5, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "x10⁹/л", "min": 4.0, "max": 9.0, "age_min": 13, "note": "взрослые"},
            {"unit": "10⁹/л", "min": 4.5, "max": 13.5, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "10⁹/л", "min": 4.0, "max": 9.0, "age_min": 13, "note": "взрослые"},
            {"unit": "109/л", "min": 4.5, "max": 13.5, "age_max": 12, "note": "дети до 12 лет"},
            {"unit": "109/л", "min": 4.0, "max": 9.0, "age_min": 13, "note": "взрослые"},
        ],
    },
    "тромбоциты": {
        "label": "Тромбоциты (PLT)",
        "rules": [
            {"unit": "х10⁹/л", "min": 180, "max": 400, "note": "взрослые"},
            {"unit": "x10⁹/л", "min": 180, "max": 400, "note": "взрослые"},
            {"unit": "10⁹/л", "min": 180, "max": 400, "note": "взрослые"},
            {"unit": "109/л", "min": 180, "max": 400, "note": "взрослые"},
        ],
    },
    "глюкоза": {
        "label": "Глюкоза (натощак)",
        "rules": [
            {"unit": "ммоль/л", "min": 3.9, "max": 5.5, "note": "взрослые, натощак"},
            {"unit": "мг/дл", "min": 70, "max": 99, "note": "взрослые, натощак"},
        ],
    },
    "натрий": {
        "label": "Натрий",
        "rules": [
            {"unit": "ммоль/л", "min": 135, "max": 145, "note": "взрослые"},
            {"unit": "мэкв/л", "min": 135, "max": 145, "note": "взрослые"},
        ],
    },
    "калий": {
        "label": "Калий",
        "rules": [
            {"unit": "ммоль/л", "min": 3.5, "max": 5.1, "note": "взрослые"},
            {"unit": "мэкв/л", "min": 3.5, "max": 5.1, "note": "взрослые"},
        ],
    },
    "кальций": {
        "label": "Кальций общий",
        "rules": [
            {"unit": "ммоль/л", "min": 2.1, "max": 2.55, "note": "взрослые, общий кальций"},
            {"unit": "мг/дл", "min": 8.4, "max": 10.2, "note": "взрослые, общий кальций"},
        ],
    },
    "креатинин": {
        "label": "Креатинин",
        "rules": [
            {"unit": "мкмоль/л", "min": 62, "max": 115, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "мкмоль/л", "min": 53, "max": 97, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "мг/дл", "min": 0.7, "max": 1.3, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "мг/дл", "min": 0.6, "max": 1.1, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "алат": {
        "label": "АЛТ (ALT)",
        "rules": [
            {"unit": "ед/л", "min": 10, "max": 41, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "ед/л", "min": 7, "max": 33, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "u/l", "min": 10, "max": 41, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "u/l", "min": 7, "max": 33, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "асat": {
        "label": "АСТ (AST)",
        "rules": [
            {"unit": "ед/л", "min": 10, "max": 40, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "ед/л", "min": 10, "max": 32, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "u/l", "min": 10, "max": 40, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "u/l", "min": 10, "max": 32, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "мно": {
        "label": "МНО (INR)",
        "rules": [
            {"unit": "", "min": 0.8, "max": 1.2, "note": "взрослые без антикоагулянтов"},
        ],
    },
    "креатининкиназа": {
        "label": "Креатининкиназа (КФК)",
        "rules": [
            {"unit": "ед/л", "min": 55, "max": 170, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "ед/л", "min": 30, "max": 135, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "u/l", "min": 55, "max": 170, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "u/l", "min": 30, "max": 135, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "тропонин": {
        "label": "Тропонин",
        "rules": [
            {"unit": "нг/мл", "max": 0.1, "note": "в норме — отрицательно (< 0,1)"},
            {"unit": "нг/л", "max": 14, "note": "высокочувствительный тест, в норме < 14"},
        ],
    },
    "билирубин": {
        "label": "Билирубин общий",
        "rules": [
            {"unit": "мкмоль/л", "min": 3.4, "max": 20.5, "note": "взрослые"},
            {"unit": "мг/дл", "min": 0.2, "max": 1.2, "note": "взрослые"},
        ],
    },
    "мочевина": {
        "label": "Мочевина",
        "rules": [
            {"unit": "ммоль/л", "min": 2.5, "max": 8.3, "note": "взрослые"},
            {"unit": "мг/дл", "min": 15, "max": 45, "note": "взрослые"},
        ],
    },
    "холестерин": {
        "label": "Холестерин общий",
        "rules": [
            {"unit": "ммоль/л", "min": 3.1, "max": 5.2, "note": "взрослые, желательно < 5,2"},
            {"unit": "мг/дл", "min": 120, "max": 200, "note": "взрослые, желательно < 200"},
        ],
    },
    "лпнп": {
        "label": "ЛПНП (LDL)",
        "rules": [
            {"unit": "ммоль/л", "max": 3.3, "note": "взрослые, желательно < 3,3; при высоком риске < 2,6"},
            {"unit": "мг/дл", "max": 130, "note": "взрослые, желательно < 130"},
        ],
    },
    "лпвп": {
        "label": "ЛПВП (HDL)",
        "rules": [
            {"unit": "ммоль/л", "min": 1.0, "sex": "m", "age_min": 18, "note": "взрослые мужчины, желательно выше"},
            {"unit": "ммоль/л", "min": 1.3, "sex": "f", "age_min": 18, "note": "взрослые женщины, желательно выше"},
            {"unit": "мг/дл", "min": 40, "sex": "m", "age_min": 18, "note": "взрослые мужчины, желательно выше"},
            {"unit": "мг/дл", "min": 50, "sex": "f", "age_min": 18, "note": "взрослые женщины, желательно выше"},
        ],
    },
    "триглицериды": {
        "label": "Триглицериды",
        "rules": [
            {"unit": "ммоль/л", "max": 1.7, "note": "взрослые, желательно < 1,7"},
            {"unit": "мг/дл", "max": 150, "note": "взрослые, желательно < 150"},
        ],
    },
    "гликированныйгемоглобин": {
        "label": "Гликированный гемоглобин (HbA1c)",
        "rules": [
            {"unit": "%", "min": 4.0, "max": 6.0, "note": "взрослые"},
            {"unit": "ммоль/моль", "min": 20, "max": 42, "note": "взрослые"},
        ],
    },
    "ферритин": {
        "label": "Ферритин",
        "rules": [
            {"unit": "мкг/л", "min": 30, "max": 400, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "мкг/л", "min": 15, "max": 150, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "нг/мл", "min": 30, "max": 400, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "нг/мл", "min": 15, "max": 150, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "среактивныйбелок": {
        "label": "С-реактивный белок (СРБ)",
        "rules": [
            {"unit": "мг/л", "max": 5, "note": "взрослые"},
        ],
    },
    "витаминд": {
        "label": "Витамин D (25-OH)",
        "rules": [
            {"unit": "нг/мл", "min": 30, "max": 100, "note": "взрослые, достаточный уровень 30–100; < 20 — дефицит"},
            {"unit": "нмоль/л", "min": 75, "max": 250, "note": "взрослые, достаточный уровень 75–250; < 50 — дефицит"},
        ],
    },
    "ттг": {
        "label": "ТТГ (TSH)",
        "rules": [
            {"unit": "мме/л", "min": 0.4, "max": 4.0, "note": "взрослые"},
            {"unit": "miu/l", "min": 0.4, "max": 4.0, "note": "взрослые"},
            {"unit": "мме/мл", "min": 0.4, "max": 4.0, "note": "взрослые"},
        ],
    },
    "т4свободный": {
        "label": "Т4 свободный",
        "rules": [
            {"unit": "пмоль/л", "min": 9, "max": 22, "note": "взрослые"},
            {"unit": "нг/дл", "min": 0.8, "max": 1.8, "note": "взрослые"},
        ],
    },
    "мочеваякислота": {
        "label": "Мочевая кислота",
        "rules": [
            {"unit": "мкмоль/л", "min": 202, "max": 416, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "мкмоль/л", "min": 142, "max": 339, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
            {"unit": "мг/дл", "min": 3.4, "max": 7.0, "sex": "m", "age_min": 18, "note": "взрослые мужчины"},
            {"unit": "мг/дл", "min": 2.4, "max": 5.7, "sex": "f", "age_min": 18, "note": "взрослые женщины"},
        ],
    },
    "альбумин": {
        "label": "Альбумин",
        "rules": [
            {"unit": "г/л", "min": 35, "max": 50, "note": "взрослые"},
        ],
    },
    "общийбелок": {
        "label": "Общий белок",
        "rules": [
            {"unit": "г/л", "min": 64, "max": 83, "note": "взрослые"},
        ],
    },
    "амилаза": {
        "label": "Амилаза",
        "rules": [
            {"unit": "ед/л", "min": 25, "max": 125, "note": "взрослые"},
            {"unit": "u/l", "min": 25, "max": 125, "note": "взрослые"},
        ],
    },
    "соэ": {
        "label": "СОЭ (ESR)",
        "rules": [
            {"unit": "мм/ч", "min": 2, "max": 10, "sex": "m", "note": "взрослые мужчины"},
            {"unit": "мм/ч", "min": 2, "max": 15, "sex": "f", "note": "взрослые женщины"},
        ],
    },
}


def normalize_sex(sex: str | None) -> str | None:
    s = (sex or "").strip().lower()
    if s in ("m", "male", "man", "муж", "мужчина", "мужской", "м"):
        return "m"
    if s in ("f", "female", "woman", "жен", "женщина", "женский", "ж"):
        return "f"
    return None


def _parse_number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def range_text(r: dict[str, Any]) -> str:
    unit = r.get("unit") or ""
    if r.get("min") is not None and r.get("max") is not None:
        return f"{r['min']}–{r['max']} {unit}".strip()
    if r.get("max") is not None:
        return f"< {r['max']} {unit}".strip()
    if r.get("min") is not None:
        return f"> {r['min']} {unit}".strip()
    return "—"


def _rule_status(r: dict[str, Any], val: float) -> str:
    if r.get("min") is not None and val < r["min"]:
        return "low"
    if r.get("max") is not None and val > r["max"]:
        return "high"
    if r.get("min") is not None or r.get("max") is not None:
        return "normal"
    return "unknown"


def check_norm(
    name: str, value: Any, unit: str = "", sex: str | None = None, age: int | None = None
) -> dict[str, Any] | None:
    """Проверяет значение показателя по справочнику норм.

    Возвращает None, если показатель неизвестен справочнику, иначе словарь:
    {"label", "value", "raw", "unit", "ranges", "status", "notes"}.
    status: "normal"|"high"|"low"|"unknown"|"ambiguous" — по применённому правилу.
    """
    key = SYNONYMS.get(critical._norm(name))
    info = NORM_RULES.get(key) if key else None
    if info is None:
        return None
    val = _parse_number(value)
    u = critical._clean_unit(unit)
    sex_key = normalize_sex(sex)

    rules = info["rules"]
    if u:
        matched = [r for r in rules if critical._clean_unit(r.get("unit", "")) == u]
        if not matched:
            matched = rules
        rules = matched

    def _specificity(r: dict[str, Any]) -> int:
        score = 0
        if "sex" in r and sex_key:
            score += 2 if r["sex"] == sex_key else -5
        if "age_min" in r or "age_max" in r:
            if age is not None:
                ok = True
                if r.get("age_min") is not None and age < r["age_min"]:
                    ok = False
                if r.get("age_max") is not None and age > r["age_max"]:
                    ok = False
                score += 1 if ok else -5
            else:
                score -= 1
        return score

    scored = sorted(rules, key=_specificity, reverse=True)
    applicable: list[dict[str, Any]] = []
    for r in scored:
        if "sex" in r and sex_key and r["sex"] != sex_key:
            continue
        if age is not None:
            if r.get("age_min") is not None and age < r["age_min"]:
                continue
            if r.get("age_max") is not None and age > r["age_max"]:
                continue
        applicable.append(r)
    if not applicable:
        applicable = scored

    status = "unknown"
    if val is not None:
        statuses = {_rule_status(r, val) for r in applicable}
        if len(applicable) == 1 or len(statuses) == 1:
            status = next(iter(statuses))
        else:
            status = "ambiguous"

    return {
        "label": info["label"],
        "value": val,
        "raw": str(value).strip(),
        "unit": u,
        "ranges": applicable,
        "status": status,
    }
