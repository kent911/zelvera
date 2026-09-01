# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
from datetime import datetime, timedelta
from typing import Any

from app.services import articles_db, audit, critical, database, embeddings, i18n, kiwix, norms, settings_store

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": i18n.t("tool.search_articles.desc"),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": i18n.t("tool.search_articles.query"),
                    },
                    "limit": {
                        "type": "integer",
                        "description": i18n.t("tool.search_articles.limit"),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_articles",
            "description": i18n.t("tool.list_articles.desc"),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": i18n.t("tool.search_wikipedia.desc"),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": i18n.t("tool.search_wikipedia.query"),
                    },
                    "limit": {
                        "type": "integer",
                        "description": i18n.t("tool.search_wikipedia.limit"),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_kiwix_books",
            "description": i18n.t("tool.list_kiwix_books.desc"),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_medical_card",
            "description": i18n.t("tool.get_medical_card.desc"),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": i18n.t("tool.get_medical_card.days"),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_marker_trends",
            "description": i18n.t("tool.get_marker_trends.desc"),
            "parameters": {
                "type": "object",
                "properties": {
                    "marker": {
                        "type": "string",
                        "description": i18n.t("tool.get_marker_trends.marker"),
                    },
                    "days": {
                        "type": "integer",
                        "description": i18n.t("tool.get_marker_trends.days"),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_marker_norm",
            "description": i18n.t("tool.check_marker_norm.desc"),
            "parameters": {
                "type": "object",
                "properties": {
                    "marker": {
                        "type": "string",
                        "description": i18n.t("tool.check_marker_norm.marker"),
                    },
                    "value": {
                        "type": "string",
                        "description": i18n.t("tool.check_marker_norm.value"),
                    },
                    "unit": {
                        "type": "string",
                        "description": i18n.t("tool.check_marker_norm.unit"),
                    },
                    "sex": {
                        "type": "string",
                        "description": i18n.t("tool.check_marker_norm.sex"),
                    },
                    "age": {
                        "type": "integer",
                        "description": i18n.t("tool.check_marker_norm.age"),
                    },
                },
                "required": ["marker", "value"],
            },
        },
    },
]


def _current_profile_id() -> int | None:
    return settings_store.get_current_profile_id()


def _filter_by_days(
    records: list[dict[str, Any]], days: int | None
) -> list[dict[str, Any]]:
    if not days or days <= 0:
        return records
    cutoff = datetime.now() - timedelta(days=int(days))

    def _parse_created(created: str) -> datetime | None:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(created, fmt)
            except ValueError:
                continue
        return None

    return [
        r
        for r in records
        if (_parse_created(r.get("created_at", "")) or datetime.min) >= cutoff
    ]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    args = arguments or {}
    audit.log_tool_call(name, args)
    try:
        if name == "search_articles":
            return await search_articles(
                str(args.get("query", "")), int(args.get("limit") or 5)
            )
        if name == "search_wikipedia":
            return await kiwix.fetch_tool_results(
                str(args.get("query", "")), int(args.get("limit") or 3)
            )
        if name == "list_kiwix_books":
            return await kiwix.fetch_books_tool_result()
        if name == "list_articles":
            return await asyncio.to_thread(list_articles)
        if name == "get_medical_card":
            return await asyncio.to_thread(
                get_medical_card, int(args.get("days")) if args.get("days") else None
            )
        if name == "get_marker_trends":
            return await asyncio.to_thread(
                get_marker_trends,
                str(args.get("marker", "")) or None,
                int(args.get("days")) if args.get("days") else None,
            )
        if name == "check_marker_norm":
            return await asyncio.to_thread(
                check_marker_norm,
                str(args.get("marker", "")),
                args.get("value"),
                str(args.get("unit", "") or ""),
                args.get("sex"),
                int(args["age"]) if args.get("age") else None,
            )
        return i18n.t("tool.unknown", name=name)
    except Exception as exc:
        return i18n.t("tool.exec_error", name=name, err=exc)


async def search_articles(query: str, limit: int = 5) -> str:
    if not query.strip():
        return i18n.t("tool.search_empty")
    try:
        (query_embedding,) = await embeddings.embed_texts([query.strip()])
    except Exception as exc:
        return i18n.t("tool.embedding_failed", err=exc)
    results = await asyncio.to_thread(
        articles_db.query, query_embedding, max(1, min(int(limit), 10))
    )
    if not results:
        return i18n.t("tool.search_no_results")
    return "\n\n".join(
        i18n.t("tool.article_ref", title=r["title"], chunk=r["chunk"])
        for r in results
    )


def list_articles() -> str:
    articles = database.list_articles()
    if not articles:
        return i18n.t("tool.articles_empty")
    return "\n".join(f"{a['id']}. {a['filename']}" for a in articles)


def get_medical_card(days: int | None = None) -> str:
    records = database.list_records(_current_profile_id())
    records = _filter_by_days(records, days)
    if not records:
        if days:
            return i18n.t("tool.no_records_days", days=days)
        return i18n.t("tool.card_empty")
    seen: dict[str, dict[str, Any]] = {}
    for rec in records:
        try:
            full = database.get_record(rec["id"])
        except KeyError:
            continue
        for m in full.get("markers", []):
            name = (m.get("name") or "").strip()
            if name and name not in seen:
                seen[name] = m
    if not seen:
        return i18n.t("tool.no_markers")
    lines: list[str] = []
    critical_found: list[str] = []
    suspect_found: list[str] = []
    for m in seen.values():
        value = m.get("value_raw") if m.get("value_raw") is not None else m.get("value")
        ref = m.get("reference_range") or "—"
        unit = m.get("unit") or ""
        status_map = {
            "high": i18n.t("tool.status.high"),
            "low": i18n.t("tool.status.low"),
            "normal": i18n.t("tool.status.normal"),
            "elevated": i18n.t("tool.status.elevated"),
        }
        status = status_map.get(m.get("status"), i18n.t("tool.status.unknown"))
        crit = None
        if not m.get("validation"):
            crit = critical.check_critical(m.get("name"), m.get("value"), m.get("unit", ""))
        if crit:
            level = i18n.t("tool.critical_level.low") if crit["level"] == "low" else i18n.t("tool.critical_level.high")
            critical_found.append(
                i18n.t(
                    "tool.critical_found",
                    name=m.get("name"),
                    value=value or "?",
                    unit=unit,
                    level=level,
                    threshold=crit["threshold"],
                    threshold_unit=crit["unit"],
                )
            )
        elif m.get("validation"):
            suspect_found.append(
                i18n.t(
                    "tool.suspect_found",
                    name=m.get("name"),
                    value=value or "?",
                    unit=unit,
                )
            )
        lines.append(
            i18n.t(
                "tool.marker_line",
                name=m.get("name"),
                value=value or "?",
                unit=unit,
                ref=ref,
                status=status,
            )
        )
    header = []
    if critical_found:
        header.append(
            i18n.t("tool.critical_header", warnings="\n".join(f"⚠ {w}" for w in critical_found))
        )
    if suspect_found:
        header.append(
            i18n.t("tool.suspect_header", warnings="\n".join(f"⚠ {w}" for w in suspect_found))
        )
    body = "\n".join(lines)
    if header:
        return "\n\n" + "\n\n".join(header) + "\n\n---\n" + body
    return body


def get_marker_trends(marker: str | None = None, days: int | None = None) -> str:
    records = database.list_records(_current_profile_id())
    records = _filter_by_days(records, days)
    if not records:
        if days:
            return i18n.t("tool.no_records_days", days=days)
        return i18n.t("tool.card_empty")
    groups: dict[str, list[tuple[str, Any]]] = {}
    for rec in records:
        try:
            full = database.get_record(rec["id"])
        except KeyError:
            continue
        for m in full.get("markers", []):
            name = (m.get("name") or "").strip()
            if not name:
                continue
            if marker and marker.lower() not in name.lower():
                continue
            value = m.get("value")
            if value is None:
                continue
            groups.setdefault(name, []).append((full.get("created_at", ""), value))
    if not groups:
        if marker:
            return i18n.t("tool.marker_not_found", marker=marker)
        return i18n.t("tool.no_numeric_markers")
    lines: list[str] = []
    for name in sorted(groups):
        pts = sorted(groups[name], key=lambda p: p[0])
        series = ", ".join(f"{d}: {v}" for d, v in pts)
        latest = pts[-1][1]
        first = pts[0][1]
        try:
            diff = float(latest) - float(first)
            if diff > 0:
                trend = i18n.t("tool.trend.up")
            elif diff < 0:
                trend = i18n.t("tool.trend.down")
            else:
                trend = i18n.t("tool.trend.stable")
        except (TypeError, ValueError):
            trend = "—"
        lines.append(
            i18n.t("tool.trend_line", name=name, series=series, n=len(pts), trend=trend)
        )
    return "\n".join(lines)


def check_marker_norm(
    marker: str,
    value: Any,
    unit: str = "",
    sex: str | None = None,
    age: int | None = None,
) -> str:
    """Проверяет показатель по справочнику референсных норм (пол/возраст)."""
    if not marker.strip():
        return i18n.t("tool.check_marker_norm.empty")
    if age is None:
        pid = _current_profile_id()
        if pid is not None:
            try:
                profile = database.get_profile(pid)
                by = profile.get("birth_year")
                if by:
                    age = datetime.now().year - int(by)
            except (KeyError, TypeError, ValueError):
                age = None
    result = norms.check_norm(marker, value, unit, sex, age)
    if result is None:
        return i18n.t("norm.not_found", marker=marker)
    if result["value"] is None:
        return i18n.t("norm.not_numeric", value=result["raw"])
    head = f"{result['label']}: {result['raw']} {result['unit']}".strip()
    if len(result["ranges"]) == 1:
        r = result["ranges"][0]
        note = f" ({r.get('note')})" if r.get("note") else ""
        status = i18n.t("norm.status." + result["status"])
        return head + "\n" + i18n.t(
            "norm.single", note=note, range=norms.range_text(r), status=status
        )
    lines = [head]
    for r in result["ranges"]:
        lines.append(
            i18n.t("norm.item", note=r.get("note") or "—", range=norms.range_text(r))
        )
    lines.append(
        i18n.t(
            "norm.multi_status",
            status=i18n.t("norm.status." + result["status"]),
        )
    )
    return "\n".join(lines)
