# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # MEDAI_DATA_DIR / MEDRIX_DATA_DIR — устаревшие имена для обратной совместимости
    data_env = (
        os.getenv("ZELVERA_DATA_DIR")
        or os.getenv("MEDRIX_DATA_DIR")
        or os.getenv("MEDAI_DATA_DIR")
    )
    default_dir = Path.home() / "zelvera-data"
    if not data_env and not default_dir.exists():
        for legacy in ("medrix-data", "medai-data"):
            legacy_dir = Path.home() / legacy
            if legacy_dir.exists():
                default_dir = legacy_dir
                break
    DATA_DIR = (
        Path(data_env).expanduser().resolve() if data_env else default_dir
    )
else:
    data_env = (
        os.getenv("ZELVERA_DATA_DIR")
        or os.getenv("MEDRIX_DATA_DIR")
        or os.getenv("MEDAI_DATA_DIR")
    )
    DATA_DIR = (
        Path(data_env).expanduser().resolve()
        if data_env
        else Path(__file__).resolve().parents[2] / "data"
    )
DB_PATH = DATA_DIR / "medical.db"
CHROMA_DIR = DATA_DIR / "chroma"
KIWIX_CACHE_DIR = DATA_DIR / "kiwix_cache"
MEDIA_DIR = DATA_DIR / "media"


class Settings:
    def __init__(self) -> None:
        self.llm_backend: str = os.getenv("LLM_BACKEND", "ollama").strip().lower()
        self.ollama_base_url: str = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        ).rstrip("/")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma4:26b").strip()
        self.ollama_vision_model: str = os.getenv(
            "OLLAMA_VISION_MODEL", "gemma4:26b"
        ).strip()
        self.ollama_embed_model: str = os.getenv(
            "OLLAMA_EMBED_MODEL", "nomic-embed-text"
        ).strip()
        self.ollama_keep_alive: str = (
            os.getenv("OLLAMA_KEEP_ALIVE", "30m").strip() or "30m"
        )
        try:
            self.ollama_num_ctx: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
        except ValueError:
            self.ollama_num_ctx = 32768
        try:
            self.ollama_vision_max_tokens: int = int(
                os.getenv("OLLAMA_VISION_MAX_TOKENS", "250")
            )
        except ValueError:
            self.ollama_vision_max_tokens = 250
        self.user_llm_base_url: str = os.getenv(
            "USER_LLM_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.user_llm_api_key: str = os.getenv("USER_LLM_API_KEY", "").strip()
        self.user_llm_model: str = os.getenv("USER_LLM_MODEL", "gpt-4o").strip()
        self.user_llm_vision_model: str = os.getenv(
            "USER_LLM_VISION_MODEL", "gpt-4o"
        ).strip()

        self.kiwix_base_url: str = os.getenv(
            "KIWIX_BASE_URL", "http://localhost:8080"
        ).rstrip("/")
        self.kiwix_zim_name: str = os.getenv("KIWIX_ZIM_NAME", "").strip()

        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_allowed_ids: str = os.getenv(
            "TELEGRAM_ALLOWED_CHAT_IDS", ""
        ).strip()
        self.telegram_voice_enabled: bool = os.getenv(
            "TELEGRAM_VOICE_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        self.telegram_whisper_model: str = os.getenv(
            "TELEGRAM_WHISPER_MODEL", "small"
        ).strip()
        self.telegram_tts_voice: str = os.getenv(
            "TELEGRAM_TTS_VOICE", "ru-RU-DmitryNeural"
        ).strip()
        self.telegram_reminders_enabled: bool = os.getenv(
            "TELEGRAM_REMINDERS_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        self.telegram_proxy: str = (
            os.getenv("TELEGRAM_PROXY", "").strip()
            or os.getenv("HTTPS_PROXY", "").strip()
            or os.getenv("https_proxy", "").strip()
            or os.getenv("ALL_PROXY", "").strip()
            or os.getenv("all_proxy", "").strip()
        )
        self.telegram_force_ipv4: bool = os.getenv(
            "TELEGRAM_FORCE_IPV4", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        self.recovery_email: str = os.getenv("RECOVERY_EMAIL", "").strip()
        self.smtp_host: str = os.getenv("SMTP_HOST", "").strip()
        self.smtp_port: str = os.getenv("SMTP_PORT", "587").strip() or "587"
        self.smtp_user: str = os.getenv("SMTP_USER", "").strip()
        self.smtp_password: str = os.getenv("SMTP_PASSWORD", "").strip()
        self.smtp_from: str = os.getenv("SMTP_FROM", "").strip()
        self.smtp_tls: bool = os.getenv("SMTP_TLS", "1").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    @property
    def active_backend(self) -> str:
        return self.llm_backend

    @property
    def active_model(self) -> str:
        if self.llm_backend == "openai":
            return self.user_llm_model
        return self.ollama_model

    @property
    def vision_model(self) -> str:
        if self.llm_backend == "openai":
            return self.user_llm_vision_model
        return self.ollama_vision_model


settings = Settings()
