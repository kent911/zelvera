# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services import audit, database, i18n
from app.services.logger import logger

router = APIRouter()


class ReminderIn(BaseModel):
    marker_name: str
    interval_days: int = Field(default=30, ge=1, le=3650)
    profile_id: int | None = None

    @field_validator("marker_name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return ""


@router.get("/reminders")
def list_reminders(profile_id: int | None = None) -> list[dict[str, Any]]:
    return database.list_reminders(profile_id)


@router.post("/reminders")
def create_reminder(body: ReminderIn) -> dict[str, Any]:
    if not body.marker_name:
        raise HTTPException(status_code=400, detail=i18n.t("reminder.marker_required"))
    if body.profile_id is not None:
        try:
            database.get_profile(body.profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=i18n.t("profile.not_found")) from exc
    result = database.create_reminder(
        marker_name=body.marker_name,
        interval_days=body.interval_days,
        profile_id=body.profile_id,
    )
    logger.info(
        "Напоминание создано: id=%s marker=%s interval=%d profile=%s",
        result["id"],
        result["marker_name"],
        result["interval_days"],
        result["profile_id"],
    )
    audit.log_action(
        "reminder_create",
        f"id={result['id']}, маркер={result['marker_name']}",
    )
    return result


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int) -> dict[str, bool]:
    if not database.delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail=i18n.t("reminder.not_found"))
    audit.log_action("reminder_delete", f"id={reminder_id}")
    return {"ok": True}
