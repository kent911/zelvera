# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError, BaseModel, field_validator

from app.services import (
    audit,
    compare,
    critical,
    database,
    i18n,
    marker_catalog,
    media_store,
    validation,
)
from app.services.logger import logger
from app.services.pdf_export import export_card_pdf

router = APIRouter()

MAX_IMAGE_BYTES = 50 * 1024 * 1024


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


def _form_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v)


def _raise_validation(exc: ValidationError) -> None:
    raise HTTPException(
        status_code=422,
        detail=[
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", "")}
            for e in exc.errors()
        ],
    ) from exc


def _save_result(rec: RecordIn, profile_id: int | None) -> dict[str, Any]:
    return database.create_record(
        source_name=rec.source_name or "manual",
        summary=rec.summary,
        markers=[m.model_dump() for m in rec.markers],
        date=rec.date,
        profile_id=profile_id,
    )


@router.get("/markers/catalog")
def markers_catalog() -> list[dict[str, Any]]:
    """Канонический справочник лабораторных показателей (имена, категории)."""
    return marker_catalog.list_catalog()


@router.get("/records/trends")
def get_trends(profile_id: int | None = None) -> list[dict[str, Any]]:
    return database.marker_trends(_require_profile(profile_id))


@router.get("/records/compare")
def compare_records(a: int, b: int) -> dict[str, Any]:
    """Построчное сравнение двух записей мед. карты (a — раньше, b — позже)."""
    try:
        first = database.get_record(a)
        second = database.get_record(b)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found")) from exc
    audit.log_action("record_compare", f"a={a}, b={b}")
    return compare.build_comparison(first, second)


@router.post("/records")
async def create_record(request: Request) -> dict[str, Any]:
    ctype = (request.headers.get("content-type") or "").lower()
    image_file: Any = None
    profile_id: int | None = None

    try:
        if ctype.startswith("multipart/form-data"):
            form = await request.form()
            raw_markers = form.get("markers")
            if isinstance(raw_markers, str) and raw_markers.strip():
                markers_data = json.loads(raw_markers)
                if not isinstance(markers_data, list):
                    markers_data = []
            else:
                markers_data = []
            raw_profile = form.get("profile_id")
            try:
                profile_id = (
                    int(raw_profile)
                    if raw_profile is not None and str(raw_profile).strip()
                    else None
                )
            except (TypeError, ValueError):
                profile_id = None
            rec = RecordIn(
                source_name=_form_str(form.get("source_name")) or "manual",
                summary=_form_str(form.get("summary")),
                date=_form_str(form.get("date")) or None,
                markers=markers_data,
                profile_id=profile_id,
            )
            image_file = form.get("original")
        else:
            body = await request.json()
            rec = RecordIn.model_validate(body)
            profile_id = rec.profile_id
    except ValidationError as exc:
        _raise_validation(exc)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = _save_result(rec, _require_profile(profile_id))

    if image_file is not None and getattr(image_file, "filename", None):
        ext = media_store.ext_from_filename(image_file.filename)
        if ext:
            content = await image_file.read()
            if content and len(content) <= MAX_IMAGE_BYTES:
                try:
                    name = media_store.save_original(result["id"], content, ext)
                    database.set_record_image(result["id"], name)
                    result = database.get_record(result["id"])
                except OSError:
                    logger.warning(
                        "Не удалось сохранить оригинал для записи %s", result["id"]
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
        if rec.get("image_path"):
            rec["image_url"] = f"/api/records/{record_id}/image"
        return rec
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found")) from exc


@router.get("/records/{record_id}/image")
def get_record_image(record_id: int) -> Response:
    try:
        rec = database.get_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found")) from exc
    name = rec.get("image_path")
    if not name:
        raise HTTPException(status_code=404, detail=i18n.t("record.image_not_found"))
    path = media_store.path_for(name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=i18n.t("record.image_not_found"))
    return FileResponse(
        path,
        media_type=media_store.mime_for(path.suffix.lstrip(".")),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.delete("/records/{record_id}")
def delete_record(record_id: int) -> dict[str, bool]:
    try:
        rec = database.get_record(record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found")) from exc
    if not database.delete_record(record_id):
        raise HTTPException(status_code=404, detail=i18n.t("record.not_found"))
    media_store.delete(rec.get("image_path"))
    audit.log_action("record_delete", f"id={record_id}")
    return {"ok": True}
