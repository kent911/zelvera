# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Долгосрочная агрегация мед. карты: показатели по годам и общая оценка.

Сервис не обращается к ИИ — это детерминированный расчёт. Результат
используется таблицей/графиком во фронтенде и как компактная сводка для
LLM-отчёта (см. routes/records.py, POST /records/longterm/report).
"""
from statistics import median
from typing import Any

from app.services import i18n, marker_catalog


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _parse_range(text: Any) -> tuple[float | None, float | None]:
    """Извлекает границы нормы из строки вида «120-160» или «< 5.0»."""
    if not text:
        return None, None
    raw = str(text).lower().replace(",", ".")
    nums: list[float] = []
    current = ""
    for ch in raw + " ":
        if ch.isdigit() or ch == ".":
            current += ch
        else:
            if current:
                try:
                    nums.append(float(current))
                except ValueError:
                    pass
                current = ""
    if len(nums) >= 2:
        low, high = min(nums[0], nums[1]), max(nums[0], nums[1])
        return low, high
    if len(nums) == 1:
        if "<" in raw:
            return None, nums[0]
        if ">" in raw:
            return nums[0], None
        return None, nums[0]
    return None, None


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def _year_of(created_at: Any) -> int | None:
    text = str(created_at or "")
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _year_status(stats: dict[str, Any], ref_low: float | None, ref_high: float | None) -> str:
    """Статус года: normal/high/low/mixed/unknown (по медиане к коридору)."""
    value = stats.get("median")
    if value is None:
        return "unknown"
    if ref_low is not None and value < ref_low:
        return "low"
    if ref_high is not None and value > ref_high:
        return "high"
    if ref_low is not None or ref_high is not None:
        return "normal"
    highs = stats.get("high", 0)
    lows = stats.get("low", 0)
    normals = stats.get("normal", 0)
    top = max(highs, lows, normals)
    if top == 0:
        return "unknown"
    if highs == top and highs > normals:
        return "high"
    if lows == top and lows > normals:
        return "low"
    if normals == top:
        return "normal"
    return "mixed"


def _flag(
    dev_years: list[str],
    status_by_year: dict[str, str],
    measured_years: list[str],
    trend: str,
) -> str:
    """Определяет обобщённый флаг по показателю за весь период."""
    if len(measured_years) < 2:
        return "insufficient"
    if not dev_years:
        if len(measured_years) >= 3 and trend == "up":
            return "trend_up"
        if len(measured_years) >= 3 and trend == "down":
            return "trend_down"
        return "stable_normal"
    last = status_by_year.get(measured_years[-1])
    prior_dev = [y for y in dev_years if y != measured_years[-1]]
    if last == "normal" and prior_dev:
        return "improving"
    if last in ("high", "low") and not prior_dev:
        return "worsening"
    ratio = len(dev_years) / len(measured_years)
    if ratio >= 0.6:
        highs = sum(1 for y in dev_years if status_by_year.get(y) == "high")
        lows = sum(1 for y in dev_years if status_by_year.get(y) == "low")
        return "persistent_high" if highs >= lows else "persistent_low"
    if ratio >= 0.3:
        return "fluctuation"
    if trend == "up":
        return "trend_up"
    if trend == "down":
        return "trend_down"
    return "fluctuation"


def build_longterm(
    records: list[dict[str, Any]],
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict[str, Any]:
    """Собирает годовую сводку по всем записям (числовые показатели)."""
    by_year: dict[int, int] = {}
    groups: dict[str, dict[str, Any]] = {}
    skipped_suspect = 0

    for rec in records or []:
        year = _year_of(rec.get("created_at"))
        if year is None:
            continue
        if year_from is not None and year < year_from:
            continue
        if year_to is not None and year > year_to:
            continue
        by_year[year] = by_year.get(year, 0) + 1
        for m in rec.get("markers", []):
            raw = (m.get("name") or "").strip()
            if not raw:
                continue
            if m.get("validation"):
                skipped_suspect += 1
                continue
            value = _num(m.get("value"))
            if value is None:
                continue
            entry = marker_catalog.entry_for(raw)
            key = entry["key"] if entry else raw.lower()
            label = entry["name"] if entry else " ".join(raw.split())
            group = groups.setdefault(
                key,
                {"name": label, "unit": m.get("unit") or "", "years": {}},
            )
            if not group.get("unit"):
                group["unit"] = m.get("unit") or ""
            ystats = group["years"].setdefault(
                year,
                {"values": [], "high": 0, "low": 0, "normal": 0, "unknown": 0},
            )
            ystats["values"].append(value)
            status = (m.get("status") or "unknown").lower()
            if status not in ("high", "low", "normal"):
                status = "unknown"
            ystats[status] += 1
            low, high = _parse_range(m.get("reference_range"))
            if low is not None:
                group.setdefault("_lows", []).append(low)
            if high is not None:
                group.setdefault("_highs", []).append(high)

    markers: list[dict[str, Any]] = []
    for group in groups.values():
        ref_low = _median(group.pop("_lows", []))
        ref_high = _median(group.pop("_highs", []))
        years_out: dict[str, dict[str, Any]] = {}
        year_medians: list[tuple[str, float]] = []
        for year in sorted(group["years"]):
            stats = group["years"][year]
            values = stats["values"]
            med = _median(values)
            item = {
                "median": med,
                "min": min(values),
                "max": max(values),
                "count": len(values),
                "high": stats["high"],
                "low": stats["low"],
                "normal": stats["normal"],
                "unknown": stats["unknown"],
            }
            item["status"] = _year_status(item, ref_low, ref_high)
            years_out[str(year)] = item
            year_medians.append((str(year), med))
        measured_years = [y for y in years_out if years_out[y]["median"] is not None]
        status_by_year = {y: years_out[y]["status"] for y in measured_years}
        dev_years = [y for y in measured_years if status_by_year[y] in ("high", "low")]
        trend = "single"
        delta_pct = None
        if len(year_medians) >= 2:
            first, last = year_medians[0][1], year_medians[-1][1]
            if first:
                delta_pct = (last - first) / first * 100
                if delta_pct > 5:
                    trend = "up"
                elif delta_pct < -5:
                    trend = "down"
                else:
                    trend = "stable"
            else:
                trend = "up" if last > first else "down" if last < first else "stable"
        markers.append(
            {
                "key": group,
                "name": group["name"],
                "unit": group["unit"],
                "ref_low": ref_low,
                "ref_high": ref_high,
                "years": years_out,
                "measured_years": len(measured_years),
                "total": sum(years_out[y]["count"] for y in years_out),
                "trend": trend,
                "delta_pct": delta_pct,
                "flag": _flag(dev_years, status_by_year, measured_years, trend),
            }
        )

    for m in markers:
        m.pop("key", None)
    markers.sort(key=lambda r: (-r["total"], r["name"].lower()))

    years = sorted(by_year)
    flags: dict[str, int] = {}
    for m in markers:
        flags[m["flag"]] = flags.get(m["flag"], 0) + 1

    return {
        "from": year_from,
        "to": year_to,
        "years": years,
        "records_by_year": {str(y): by_year[y] for y in years},
        "records_total": sum(by_year.values()),
        "markers": markers,
        "summary": {
            "markers_total": len(markers),
            "flags": flags,
            "skipped_suspect": skipped_suspect,
        },
    }


def flag_label(code: str) -> str:
    return i18n.t(f"longterm.flag.{code}")


def to_prompt_text(data: dict[str, Any], max_markers: int = 40) -> str:
    """Компактная сводка для LLM: годы, показатели, медианы, флаги."""
    lines: list[str] = []
    years = data.get("years") or []
    if years:
        span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
        lines.append(i18n.t("longterm.prompt.span", span=span))
        counts = ", ".join(
            i18n.t("longterm.prompt.year_count", year=y, n=data["records_by_year"][str(y)])
            for y in years
        )
        lines.append(i18n.t("longterm.prompt.records", counts=counts))
    lines.append("")
    for m in (data.get("markers") or [])[:max_markers]:
        ref = "—"
        if m.get("ref_low") is not None and m.get("ref_high") is not None:
            ref = f"{m['ref_low']:g}-{m['ref_high']:g}"
        elif m.get("ref_high") is not None:
            ref = f"<{m['ref_high']:g}"
        elif m.get("ref_low") is not None:
            ref = f">{m['ref_low']:g}"
        head = i18n.t(
            "longterm.prompt.marker",
            name=m["name"],
            unit=m.get("unit") or "—",
            ref=ref,
            flag=flag_label(m["flag"]),
            n=m["total"],
        )
        lines.append(head)
        parts: list[str] = []
        for y in years:
            st = m["years"].get(str(y))
            if not st or st.get("median") is None:
                continue
            parts.append(
                i18n.t(
                    "longterm.prompt.year_value",
                    year=y,
                    median=f"{st['median']:g}",
                    n=st["count"],
                    status=i18n.t(f"longterm.status.{st['status']}"),
                )
            )
        if parts:
            lines.append("  " + "; ".join(parts))
    return "\n".join(lines)
