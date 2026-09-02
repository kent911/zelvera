# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import httpx

from app.config import DATA_DIR, settings as env_settings
from app.services import audit, i18n, kiwix, settings_store

router = APIRouter()


class SettingsUpdate(BaseModel):
    ollama_base_url: str | None = None
    chat_model: str | None = None
    vision_model: str | None = None
    embed_model: str | None = None
    num_ctx: str | None = None
    kiwix_base_url: str | None = None
    kiwix_zim_name: str | None = None
    lang: str | None = None


class BaseUrlIn(BaseModel):
    ollama_base_url: str


@router.get("/settings")
async def get_settings() -> dict[str, str]:
    data = settings_store.all_settings()
    data["backend"] = env_settings.llm_backend
    data["data_dir"] = str(DATA_DIR)
    return data


@router.post("/settings")
async def update_settings(body: SettingsUpdate) -> dict[str, str]:
    saved = settings_store.update(
        **{k: v for k, v in body.model_dump().items() if v is not None}
    )
    i18n.set_lang(saved.get("lang", i18n.get_lang()))
    saved["backend"] = env_settings.llm_backend
    audit.log_action("settings_update", f"модель={saved.get('chat_model')}")
    return saved


@router.post("/settings/ollama-models")
async def ollama_models(body: BaseUrlIn) -> dict[str, Any]:
    try:
        models = await settings_store.list_ollama_models(body.ollama_base_url)
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"models": models}


class KiwixBaseUrlIn(BaseModel):
    kiwix_base_url: str


@router.post("/settings/kiwix-books")
async def kiwix_books(body: KiwixBaseUrlIn) -> dict[str, Any]:
    """Проверяет связь с kiwix-serve и возвращает список доступных ZIM-книг."""
    url = body.kiwix_base_url.strip().rstrip("/")
    if not url:
        raise HTTPException(status_code=400, detail=i18n.t("settings.kiwix_url_required"))
    try:
        if settings_store.get("kiwix_base_url") != url:
            settings_store.update(kiwix_base_url=url)
        books = await kiwix.get_books()
    except kiwix.KiwixError as exc:
        raise HTTPException(status_code=502, detail=i18n.t(exc.key)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    audit.log_action("settings_update", "kiwix: проверка списка книг")
    return {"books": books}
