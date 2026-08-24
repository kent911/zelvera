# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.services import audit, database, i18n
from app.services.logger import logger
from app.services import settings_store

router = APIRouter()


class ProfileIn(BaseModel):
    name: str
    birth_year: int | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    blood_type: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return ""

    @field_validator("birth_year", "height_cm", mode="before")
    @classmethod
    def _clean_int(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("weight_kg", mode="before")
    @classmethod
    def _clean_float(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        return float(str(v).replace(",", "."))

    @field_validator("blood_type", mode="before")
    @classmethod
    def _clean_blood_type(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        # "a(ii) rh+" -> "A(II) Rh+", "o(i)" -> "O(I)"
        s = s.replace("rh+", "Rh+").replace("rh-", "Rh-").replace("RH+", "Rh+").replace("RH-", "Rh-")
        return s[:1].upper() + s[1:]


def _profile_ids() -> list[int]:
    return [p["id"] for p in database.list_profiles()]


def get_current_profile() -> dict[str, Any]:
    """Текущий профиль: из настроек, с фолбэком на первый существующий."""
    profiles = database.list_profiles()
    if not profiles:
        raise HTTPException(status_code=500, detail=i18n.t("profile.no_profiles"))
    ids = [p["id"] for p in profiles]
    current = settings_store.get_current_profile_id()
    if current not in ids:
        current = ids[0]
        settings_store.set_current_profile_id(current)
    profile = next(p for p in profiles if p["id"] == current)
    return profile


def _set_current(profile_id: int) -> None:
    if profile_id not in _profile_ids():
        raise HTTPException(status_code=404, detail=i18n.t("profile.not_found"))
    settings_store.set_current_profile_id(profile_id)


@router.get("/profiles")
def list_profiles() -> dict[str, Any]:
    profiles = database.list_profiles()
    current = get_current_profile()
    return {"profiles": profiles, "current": current["id"]}


@router.post("/profiles")
def create_profile(body: ProfileIn) -> dict[str, Any]:
    raise HTTPException(
        status_code=403,
        detail=i18n.t("profile.single_only"),
    )


@router.patch("/profiles/{profile_id}")
def rename_profile(profile_id: int, body: ProfileIn) -> dict[str, Any]:
    if not body.name:
        raise HTTPException(status_code=400, detail=i18n.t("profile.name_required"))
    if not database.update_profile(
        profile_id,
        body.name,
        birth_year=body.birth_year,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        blood_type=body.blood_type,
    ):
        raise HTTPException(status_code=404, detail=i18n.t("profile.not_found"))
    logger.info("Профиль обновлён: id=%s name=%s", profile_id, body.name)
    audit.log_action("profile_update", f"id={profile_id}, name={body.name}")
    return database.get_profile(profile_id)


@router.post("/profiles/{profile_id}/activate")
def activate_profile(profile_id: int) -> dict[str, Any]:
    _set_current(profile_id)
    audit.log_action("profile_activate", f"id={profile_id}")
    return get_current_profile()


@router.get("/profiles/current")
def current_profile() -> dict[str, Any]:
    return get_current_profile()


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int) -> dict[str, bool]:
    raise HTTPException(
        status_code=403,
        detail=i18n.t("profile.single_no_delete"),
    )
