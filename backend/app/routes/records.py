# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from app.services import audit, critical, database, i18n, validation
from app.services.logger import logger
from app.services.pdf_export import export_card_pdf

router = APIRouter()


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return v.strip()
    return ""


class MarkerIn(BaseModel):
    name: str
    value: float | str | None = None
    unit: str = ""
    reference_range: str = ""
    status: str = "unknown"

    @field_validator("name", mode="before")
    @classmethod
    def _coerce_name(cls, v: Any) -> str:
        return _clean_str(v)

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> float | str | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            return v.strip() or None
        return None

    @field_validator("unit", "reference_range", mode="before")
    @classmethod
    def _coerce_text(cls, v: Any) -> str:
        return _clean_str(v)

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> str:
        s = _clean_str(v).lower()
        return s if s in {"normal", "high", "low", "elevated", "unknown"} else "unknown"


class RecordIn(BaseModel):
    source_name: str = "manual"
    summary: str = ""
    date: str | None = None
    markers: list[MarkerIn] = []
    profile_id: int | None = None


def _require_profile(profile_id: int | None) -> int | None:
    if profile_id is None:
        return None
    try:
        database.get_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("profile.not_found")) from exc
    return profile_id


@router.get("/records/trends")
def get_trends(profile_id: int | None = None) -> list[dict[str, Any]]:
    return database.marker_trends(_require_profile(profile_id))


@router.post("/records")
def create_record(rec: RecordIn) -> dict[str, Any]:
    result = database.create_record(
        source_name=rec.source_name or "manual",
        summary=rec.summary,
        markers=[m.model_dump() for m in rec.markers],
        date=rec.date,
        profile_id=rec.profile_id,
    )
    logger.info("Запись создана: id=%s (маркеров=%d)", result["id"], len(result["markers"]))
    audit.log_action(
        "record_create",
        f"id={result['id']}, маркеров={len(result['markers'])}",
    )
    return result


@router.get("/records")
def list_records(profile_id: int | None = None) -> list[dict[str, Any]]:
    records = database.list_records(_require_profile(profile_id))
    markers_map = database.markers_for_records([r["id"] for r in records])
    for rec in records:
        flagged = critical.flag_markers(markers_map.get(rec["id"], []))
        flagged = validation.enrich_markers(flagged)
        rec["critical_count"] = sum(1 for m in flagged if m.get("critical"))
    return records


@router.get("/records/export.pdf")
def export_pdf(profile_id: int | None = None) -> Response:
    records = [
        database.get_record(r["id"])
        for r in database.list_records(_require_profile(profile_id))
    ]
    payload = export_card_pdf(records)
    audit.log_action("export_pdf", f"записей: {len(records)}")
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="med-card.pdf"',
        },
    )


@router.get("/records/{record_id}")
def get_record(record_id: int) -> dict[str, Any]:
    try:
        rec = database.get_record(record_id)
        rec["markers"] = critical.flag_markers(rec["markers"])
        rec["markers"] = validation.enrich_markers(rec["markers"])
        return rec
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found")) from exc


@router.delete("/records/{record_id}")
def delete_record(record_id: int) -> dict[str, bool]:
    if not database.delete_record(record_id):
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found"))
    audit.log_action("record_delete", f"id={record_id}")
    return {"ok": True}
