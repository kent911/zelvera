# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Опциональные голосовые возможности Telegram-бота.

Распознавание речи (STT) — faster-whisper, синтез (TTS) — edge-tts.
Оба пакета необязательны: если не установлены, функции возвращают
признак недоступности, а бот продолжает работать в текстовом режиме.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.services.logger import logger

_stt_model = None
_stt_model_name = ""


def stt_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
    except Exception:
        return False
    return True


def _get_model(model_name: str):
    global _stt_model, _stt_model_name
    if _stt_model is None or _stt_model_name != model_name:
        from faster_whisper import WhisperModel

        logger.info("Telegram STT: загрузка модели faster-whisper '%s'", model_name)
        _stt_model = WhisperModel(model_name, device="auto", compute_type="int8")
        _stt_model_name = model_name
    return _stt_model


def _transcribe_sync(data: bytes, model_name: str) -> str:
    model = _get_model(model_name)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        segments, _info = model.transcribe(path, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


async def transcribe(data: bytes, model_name: str = "small") -> str:
    """Распознаёт голосовое сообщение (ogg/opus) в текст."""
    return await asyncio.to_thread(_transcribe_sync, data, model_name)


async def synthesize(text: str, voice: str = "ru-RU-DmitryNeural") -> bytes:
    """Синтезирует речь (mp3). Пустая строка, если TTS недоступен."""
    if not text.strip() or not tts_available():
        return b""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            buffer.extend(chunk.get("data", b""))
    return bytes(buffer)
