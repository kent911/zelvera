# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Runtime-настройки моделей Ollama (persist в data/settings.json).

Приоритет: настройки, сохранённые пользователем > значения из .env.
"""
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import DATA_DIR, settings as env_settings

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "ollama_base_url": env_settings.ollama_base_url,
    "chat_model": env_settings.ollama_model,
    "vision_model": env_settings.ollama_vision_model,
    "embed_model": env_settings.ollama_embed_model,
    "num_ctx": str(env_settings.ollama_num_ctx),
    "vision_max_tokens": str(env_settings.ollama_vision_max_tokens),
    "kiwix_base_url": env_settings.kiwix_base_url,
    "kiwix_zim_name": env_settings.kiwix_zim_name,
    "telegram_bot_token": env_settings.telegram_bot_token,
    "telegram_allowed_ids": env_settings.telegram_allowed_ids,
    "telegram_voice_enabled": "1" if env_settings.telegram_voice_enabled else "0",
    "telegram_whisper_model": env_settings.telegram_whisper_model,
    "telegram_tts_voice": env_settings.telegram_tts_voice,
    "telegram_reminders_enabled": (
        "1" if env_settings.telegram_reminders_enabled else "0"
    ),
    "telegram_offset": "0",
    "telegram_proxy": env_settings.telegram_proxy,
    "telegram_force_ipv4": "1" if env_settings.telegram_force_ipv4 else "0",
    "current_profile_id": "",
    "lang": "ru",
}

_cache: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _cache
    if _cache is None:
        saved: dict[str, Any] = {}
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            saved = {}
        merged = dict(DEFAULTS)
        for key, value in saved.items():
            if key in DEFAULTS and isinstance(value, str) and value.strip():
                merged[key] = value.strip()
        _cache = merged
    return _cache


def get(key: str) -> str:
    return _load()[key]


def all_settings() -> dict[str, str]:
    return dict(_load())


def update(**kwargs: str) -> dict[str, str]:
    current = _load()
    changed = False
    for key, value in kwargs.items():
        if key in DEFAULTS and value and value.strip() != current.get(key):
            current[key] = value.strip()
            changed = True
    if changed:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return dict(current)


async def list_ollama_models(base_url: str) -> list[str]:
    from app.services.i18n import t

    url = f"{base_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ConnectionError(
                t("settings.ollama_unreachable", url=base_url, err=exc)
            ) from exc
    models = data.get("models", [])
    return [m.get("name", "") for m in models if m.get("name")]


def get_current_profile_id() -> int | None:
    value = _load().get("current_profile_id", "")
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


def set_current_profile_id(profile_id: int) -> None:
    update(current_profile_id=str(profile_id))
