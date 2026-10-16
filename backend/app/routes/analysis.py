# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.services import articles_db, audit, database, embeddings, i18n, llm

router = APIRouter()


def _latest_markers(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for rec in records:
        for m in rec.get("markers", []):
            name = (m.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen[name] = m
    return list(seen.values())


def _marker_line(m: dict[str, Any]) -> str:
    value = m.get("value_raw") or m.get("value")
    parts = [
        m.get("name"),
        f"{value} {m.get('unit', '')}".strip() if value is not None else i18n.t("marker.no_value"),
    ]
    if m.get("reference_range"):
        parts.append(i18n.t("marker.norm", ref=m["reference_range"]))
    status = m.get("status")
    status_map = {
        "high": i18n.t("marker.status.high"),
        "low": i18n.t("marker.status.low"),
        "normal": i18n.t("marker.status.normal"),
    }
    parts.append(status_map.get(status, i18n.t("marker.status.unknown")))
    return " · ".join(parts)


@router.post("/analysis")
async def analysis(request: Request, profile_id: int | None = None) -> StreamingResponse:
    if profile_id is not None:
        try:
            database.get_profile(profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=i18n.t("profile.not_found")) from exc
    records = await asyncio.to_thread(database.list_records, profile_id)
    if not records:
        raise HTTPException(
            status_code=400,
            detail=i18n.t("analysis.card_empty"),
        )
    audit.log_action("analysis", f"записей в карте: {len(records)}")

    full_records: list[dict[str, Any]] = []
    for rec in records:
        try:
            full_records.append(
                await asyncio.to_thread(database.get_record, rec["id"])
            )
        except KeyError:
            continue

    markers = _latest_markers(full_records)
    if not markers:
        raise HTTPException(
            status_code=400, detail=i18n.t("analysis.no_markers")
        )
    markers_text = "\n".join(f"- {_marker_line(m)}" for m in markers)

    search_query = " ".join(f"{m.get('name', '')} {m.get('value_raw', '')}" for m in markers)

    article_results: list[dict[str, Any]] = []
    try:
        (query_embedding,) = await embeddings.embed_texts([search_query.strip() or "анализы крови"])
        article_results = await asyncio.to_thread(
            articles_db.hybrid_query, search_query.strip() or "анализы крови", query_embedding, 3
        )
    except llm.LLMError:
        article_results = []

    if article_results:
        articles_text = "\n\n".join(
            i18n.t("analysis.article_ref", title=r["title"], chunk=r["chunk"])
            for r in article_results
        )
    else:
        articles_text = i18n.t("analysis.articles_not_found")

    messages = [
        {"role": "system", "content": i18n.t("analysis_system")},
        {
            "role": "user",
            "content": i18n.t("analysis_user", markers_text=markers_text, articles_text=articles_text),
        },
    ]

    async def event_stream():
        if not article_results:
            yield _sse(i18n.t("analysis.no_articles_note"))
        try:
            async for chunk in llm.stream_chat(messages):
                if await request.is_disconnected():
                    return
                yield _sse(chunk)
        except asyncio.CancelledError:
            return
        except llm.LLMError as exc:
            yield _sse(f"{i18n.t('error.prefix')} {exc}")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(text: str) -> str:
    return f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
