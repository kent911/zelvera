# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Сравнение двух записей мед. карты: какие показатели изменились между анализами."""
from typing import Any

from app.services import marker_catalog


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _index(markers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Сопоставляет маркеры по каноническому ключу (или имени в нижнем регистре)."""
    result: dict[str, dict[str, Any]] = {}
    for m in markers or []:
        raw = (m.get("name") or "").strip()
        if not raw:
            continue
        entry = marker_catalog.entry_for(raw)
        key = entry["key"] if entry else raw.lower()
        result[key] = {**m, "name": entry["name"] if entry else " ".join(raw.split())}
    return result


def _display(marker: dict[str, Any] | None) -> Any:
    if not marker:
        return None
    if marker.get("value") is not None:
        return marker.get("value")
    return marker.get("value_raw")


def build_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Строит построчное сравнение двух записей.

    change: up/down/stable (числовое изменение), appeared/disappeared
    (показатель есть только в одной записи), unknown (значения не числа).
    """
    amap = _index(a.get("markers", []))
    bmap = _index(b.get("markers", []))
    rows: list[dict[str, Any]] = []
    for key in dict.fromkeys([*amap, *bmap]):
        ma, mb = amap.get(key), bmap.get(key)
        ref = ma or mb or {}
        va = _num(ma.get("value")) if ma else None
        vb = _num(mb.get("value")) if mb else None
        delta: float | None = None
        pct: float | None = None
        if va is not None and vb is not None:
            delta = vb - va
            if va != 0:
                pct = delta / va * 100
        if ma is None:
            change = "appeared"
        elif mb is None:
            change = "disappeared"
        elif delta is None:
            change = "unknown"
        elif abs(delta) < 1e-9:
            change = "stable"
        else:
            change = "up" if delta > 0 else "down"
        rows.append(
            {
                "name": ref.get("name") or key,
                "unit": ref.get("unit") or "",
                "value_a": _display(ma),
                "value_b": _display(mb),
                "status_a": (ma or {}).get("status") or "unknown",
                "status_b": (mb or {}).get("status") or "unknown",
                "delta": delta,
                "delta_pct": pct,
                "change": change,
            }
        )
    rows.sort(key=lambda r: r["name"].lower())
    summary: dict[str, int] = {"total": len(rows)}
    for row in rows:
        summary[row["change"]] = summary.get(row["change"], 0) + 1
    return {
        "a": {
            "id": a.get("id"),
            "date": a.get("created_at"),
            "source": a.get("source_name"),
        },
        "b": {
            "id": b.get("id"),
            "date": b.get("created_at"),
            "source": b.get("source_name"),
        },
        "markers": rows,
        "summary": summary,
    }
