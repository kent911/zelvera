# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from pathlib import Path

from app.config import MEDIA_DIR
from app.services.logger import logger

_EXT_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
}

ALLOWED_EXTS = set(_EXT_MIME)


def ensure_dir() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def ext_from_filename(filename: str) -> str | None:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    return ext if ext in ALLOWED_EXTS else None


def mime_for(ext: str) -> str:
    return _EXT_MIME.get(ext.lower().lstrip("."), "application/octet-stream")


def filename_for(record_id: int, ext: str) -> str:
    return f"{record_id}.{ext.lower().lstrip('.')}"


def path_for(filename: str) -> Path:
    return MEDIA_DIR / Path(filename).name


def save_original(record_id: int, content: bytes, ext: str) -> str:
    ensure_dir()
    name = filename_for(record_id, ext)
    path = path_for(name)
    path.write_bytes(content)
    logger.info("Оригинал анализа сохранён: %s (%d байт)", name, len(content))
    return name


def delete(filename: str | None) -> None:
    if not filename:
        return
    path = path_for(filename)
    try:
        if path.is_file():
            path.unlink()
            logger.info("Оригинал анализа удалён: %s", path.name)
    except OSError:
        logger.warning("Не удалось удалить файл оригинала: %s", path)
