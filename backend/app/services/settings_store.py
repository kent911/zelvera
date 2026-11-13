# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Runtime-настройки моделей (persist в data/settings.json).

Приоритет: настройки, сохранённые пользователем > значения из .env.
"""
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import DATA_DIR, settings as env_settings
from app.services import net

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "llm_backend": env_settings.llm_backend,
    "openai_base_url": env_settings.user_llm_base_url,
    "openai_api_key": env_settings.user_llm_api_key or "local",
    "lmstudio_base_url": env_settings.lmstudio_base_url,
    "lmstudio_api_key": "local",
    "ollama_base_url": env_settings.ollama_base_url,
    "chat_model": env_settings.ollama_model,
    "vision_backend": "",
    "vision_model": env_settings.ollama_vision_model,
    "embed_model": env_settings.ollama_embed_model,
    "num_ctx": str(env_settings.ollama_num_ctx),
    "ollama_keep_alive": env_settings.ollama_keep_alive,
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
    "github_proxy": env_settings.github_proxy,
    "suggest_chips": "",
    "recovery_email": env_settings.recovery_email,
    "smtp_host": env_settings.smtp_host,
    "smtp_port": env_settings.smtp_port,
    "smtp_user": env_settings.smtp_user,
    "smtp_password": env_settings.smtp_password,
    "smtp_from": env_settings.smtp_from,
    "smtp_tls": "1" if env_settings.smtp_tls else "0",
    "current_profile_id": "",
    "lang": "ru",
}

_cache: dict[str, str] | None = None

ALLOW_EMPTY_KEYS = {
    "vision_backend",
    "suggest_chips",
    "recovery_email",
    "smtp_host",
    "smtp_user",
    "smtp_password",
    "smtp_from",
    "github_proxy",
}

SECRET_KEYS = (
    "openai_api_key",
    "lmstudio_api_key",
    "telegram_bot_token",
    "smtp_password",
)
KEEP_IF_BLANK_KEYS = SECRET_KEYS


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
            if not (key in DEFAULTS and isinstance(value, str)):
                continue
            if value.strip() or key in ALLOW_EMPTY_KEYS:
                merged[key] = value.strip()
        _cache = merged
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


def get(key: str) -> str:
    return _load()[key]


def all_settings() -> dict[str, str]:
    return dict(_load())


def public_settings() -> dict[str, str]:
    data = dict(_load())
    for key in SECRET_KEYS:
        stored = (data.get(key) or "").strip()
        data[f"{key}_set"] = (
            "1" if stored and stored != "local" else "0"
        )
        data[key] = ""
    return data


BACKENDS = ("ollama", "openai", "lmstudio")


def llm_backend() -> str:
    value = (_load().get("llm_backend") or env_settings.llm_backend or "ollama").strip().lower()
    return value if value in BACKENDS else "ollama"


def vision_backend() -> str:
    """Движок для фото. Пусто — как у чата; иначе ollama, openai или lmstudio."""
    value = (_load().get("vision_backend") or "").strip().lower()
    if value in BACKENDS:
        return value
    return llm_backend()


def openai_base_url() -> str:
    """Адрес OpenAI-совместимого API: OpenAI/llama-server или LM Studio."""
    if llm_backend() == "lmstudio":
        url = (
            _load().get("lmstudio_base_url")
            or env_settings.lmstudio_base_url
            or ""
        ).strip().rstrip("/")
        if not url:
            url = "http://127.0.0.1:1234"
    else:
        url = (
            _load().get("openai_base_url")
            or env_settings.user_llm_base_url
            or ""
        ).strip().rstrip("/")
        if not url:
            url = "http://127.0.0.1:8080"
    if url.endswith("/v1"):
        return url
    return url + "/v1"


def openai_api_key() -> str:
    if llm_backend() == "lmstudio":
        key = (_load().get("lmstudio_api_key") or "").strip()
    else:
        key = (
            _load().get("openai_api_key")
            or env_settings.user_llm_api_key
            or ""
        ).strip()
    return key or "local"


def normalize_openai_base_url(url: str) -> str:
    value = (url or "").strip().rstrip("/")
    if not value:
        return ""
    if value.endswith("/v1"):
        return value
    return value + "/v1"


SUGGEST_CHIPS_MAX = 12
SUGGEST_CHIP_MAX_LEN = 200


def _clean_suggest_chips(raw: str) -> str:
    """JSON-массив строк: обрезаем пустые, длину и количество."""
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, list):
        return ""
    items: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        value = item.strip()[:SUGGEST_CHIP_MAX_LEN]
        if value:
            items.append(value)
        if len(items) >= SUGGEST_CHIPS_MAX:
            break
    return json.dumps(items, ensure_ascii=False)


def suggest_chips() -> list[str]:
    """Быстрые вопросы из настроек. Пусто — используются значения по умолчанию."""
    cleaned = _clean_suggest_chips(_load().get("suggest_chips") or "")
    if not cleaned:
        return []
    return list(json.loads(cleaned))


def update(**kwargs: str) -> dict[str, str]:
    current = _load()
    changed = False
    for key, value in kwargs.items():
        if key not in DEFAULTS or value is None:
            continue
        stripped = value.strip()
        if key in KEEP_IF_BLANK_KEYS and not stripped:
            continue
        if key in ("openai_base_url", "lmstudio_base_url") and stripped:
            stripped = normalize_openai_base_url(stripped)
        if key == "suggest_chips":
            stripped = _clean_suggest_chips(stripped)
        if key == "llm_backend":
            stripped = stripped.lower()
            if stripped not in BACKENDS:
                stripped = "ollama"
        if key == "vision_backend":
            stripped = stripped.lower()
            if stripped not in BACKENDS:
                stripped = ""
        if (stripped or key in ALLOW_EMPTY_KEYS) and stripped != current.get(key):
            current[key] = stripped
            changed = True
    if changed:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return dict(current)


async def list_openai_models(base_url: str, api_key: str = "") -> list[str]:
    from app.services.i18n import t

    url = normalize_openai_base_url(base_url)
    if not url:
        raise ConnectionError(t("settings.openai_url_required"))
    headers = {"Authorization": f"Bearer {(api_key or 'local').strip() or 'local'}"}
    async with net.async_client(url, timeout=10) as client:
        try:
            resp = await client.get(f"{url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ConnectionError(
                t("settings.openai_unreachable", url=url, err=exc)
            ) from exc
    raw = data.get("data") or data.get("models") or []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if name:
                names.append(str(name))
    return names


async def list_ollama_models(base_url: str) -> list[str]:
    from app.services.i18n import t

    url = f"{base_url.rstrip('/')}/api/tags"
    async with net.async_client(url, timeout=10) as client:
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


async def probe_llm() -> dict[str, str | bool]:
    """Пинг выбранного чат-движка. Не бросает: UI красит точку по reachable."""
    backend = llm_backend()
    model = get("chat_model")
    result: dict[str, str | bool] = {
        "backend": backend,
        "model": model,
        "reachable": False,
        "error": "",
    }
    try:
        if backend in ("openai", "lmstudio"):
            names = await list_openai_models(openai_base_url(), openai_api_key())
        else:
            names = await list_ollama_models(get("ollama_base_url"))
        result["reachable"] = True
        if model and names and model not in names:
            result["error"] = "model"
    except ConnectionError as exc:
        result["error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def get_current_profile_id() -> int | None:
    value = _load().get("current_profile_id", "")
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


def set_current_profile_id(profile_id: int) -> None:
    update(current_profile_id=str(profile_id))
