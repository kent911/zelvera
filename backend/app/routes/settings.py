# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import DATA_DIR, settings as env_settings
from app.services import audit, i18n, settings_store

router = APIRouter()


class SettingsUpdate(BaseModel):
    ollama_base_url: str | None = None
    chat_model: str | None = None
    vision_model: str | None = None
    embed_model: str | None = None
    num_ctx: str | None = None
    lang: str | None = None


class BaseUrlIn(BaseModel):
    ollama_base_url: str


class PullIn(BaseModel):
    ollama_base_url: str
    model: str


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


@router.post("/settings/ollama-pull")
async def start_pull(body: PullIn) -> dict[str, Any]:
    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail=i18n.t("settings.model_required"))
    audit.log_action("model_pull", f"модель={model}")
    return settings_store.start_pull(body.ollama_base_url, model)


@router.get("/settings/ollama-pull/{model}")
async def pull_status(model: str) -> dict[str, Any]:
    return settings_store.get_pull_status(model)
