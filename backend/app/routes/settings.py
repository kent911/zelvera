# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import httpx

from app.config import DATA_DIR
from app.services import audit, i18n, kiwix, settings_store

router = APIRouter()


class SettingsUpdate(BaseModel):
    llm_backend: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    chat_model: str | None = None
    vision_backend: str | None = None
    vision_model: str | None = None
    embed_model: str | None = None
    num_ctx: str | None = None
    kiwix_base_url: str | None = None
    kiwix_zim_name: str | None = None
    lang: str | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_ids: str | None = None
    telegram_voice_enabled: str | None = None
    telegram_whisper_model: str | None = None
    telegram_tts_voice: str | None = None
    telegram_reminders_enabled: str | None = None
    telegram_proxy: str | None = None
    telegram_force_ipv4: str | None = None


class BaseUrlIn(BaseModel):
    ollama_base_url: str


class OpenAIUrlIn(BaseModel):
    openai_base_url: str
    openai_api_key: str | None = None


@router.get("/settings")
async def get_settings() -> dict[str, str]:
    data = settings_store.all_settings()
    data["backend"] = settings_store.llm_backend()
    data["data_dir"] = str(DATA_DIR)
    return data


@router.post("/settings")
async def update_settings(body: SettingsUpdate) -> dict[str, str]:
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    saved = settings_store.update(**values)
    i18n.set_lang(saved.get("lang", i18n.get_lang()))
    saved["backend"] = settings_store.llm_backend()
    audit.log_action(
        "settings_update",
        f"backend={saved.get('llm_backend')} модель={saved.get('chat_model')}",
    )
    if any(key.startswith("telegram_") for key in values):
        from app.services.telegram_bot import bot as telegram_bot

        await telegram_bot.restart()
    return saved


@router.post("/settings/ollama-models")
async def ollama_models(body: BaseUrlIn) -> dict[str, Any]:
    try:
        models = await settings_store.list_ollama_models(body.ollama_base_url)
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"models": models}


@router.post("/settings/openai-models")
async def openai_models(body: OpenAIUrlIn) -> dict[str, Any]:
    try:
        models = await settings_store.list_openai_models(
            body.openai_base_url, body.openai_api_key or ""
        )
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


class TelegramTokenIn(BaseModel):
    telegram_bot_token: str


@router.post("/settings/telegram-test")
async def telegram_test(body: TelegramTokenIn) -> dict[str, Any]:
    """Проверяет токен бота через getMe и возвращает имя/ID бота."""
    token = body.telegram_bot_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail=i18n.t("settings.telegram_token_required"))
    try:
        opts: dict[str, Any] = {}
        proxy = (settings_store.get("telegram_proxy") or "").strip()
        if proxy:
            opts["proxy"] = proxy
        elif (settings_store.get("telegram_force_ipv4") or "1").strip() == "1":
            opts["transport"] = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(timeout=15, **opts) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        err = f"{type(exc).__name__}: {exc}".strip().rstrip(":")
        raise HTTPException(
            status_code=502,
            detail=i18n.t("settings.telegram_unreachable", err=err),
        ) from exc
    if not data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=str(data.get("description") or i18n.t("settings.telegram_token_invalid")),
        )
    result = data.get("result") or {}
    audit.log_action("settings_update", "telegram: проверка токена")
    return {"username": result.get("username", ""), "id": result.get("id")}


@router.get("/settings/telegram-status")
async def telegram_status() -> dict[str, Any]:
    from app.services import voice
    from app.services.telegram_bot import bot as telegram_bot

    return {
        "configured": telegram_bot.is_configured(),
        "running": bool(telegram_bot._task and not telegram_bot._task.done()),
        "recipients": len(telegram_bot.allowed_ids()),
        "stt_available": voice.stt_available(),
        "tts_available": voice.tts_available(),
    }

