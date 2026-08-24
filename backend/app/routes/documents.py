# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import audit, document, extractor, i18n, llm, validation
from app.services.logger import logger

router = APIRouter()

IMAGE_EXTS = {"png", "jpeg", "jpg", "webp", "gif", "bmp", "tiff", "tif"}
DOC_EXTS = {"pdf", "docx"}

MIME_MAP = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
}

MAX_BYTES = 50 * 1024 * 1024


@router.post("/documents/extract")
async def extract_document(file: UploadFile = File(...)) -> dict:
    ext = document.guess_ext(file.filename or "")
    if ext not in IMAGE_EXTS | DOC_EXTS:
        raise HTTPException(
            status_code=415,
            detail=i18n.t(
                "documents.unsupported",
                exts=", ".join(sorted(IMAGE_EXTS | DOC_EXTS)),
            ),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=i18n.t("documents.empty_file"))
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail=i18n.t("documents.too_large")
        )

    try:
        if ext in IMAGE_EXTS:
            image_b64 = document.encode_image_bytes(BytesIO(content))
            text = await llm.ocr_image(image_b64, MIME_MAP.get(ext, "image/jpeg"))
        elif ext == "pdf":
            text = document.extract_text_from_pdf(BytesIO(content))
        else:
            text = document.extract_text_from_docx(BytesIO(content))
    except document.DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not text.strip():
        raise HTTPException(
            status_code=422, detail=i18n.t("documents.extract_failed")
        )

    try:
        parsed = await extractor.extract_markers(text)
    except llm.LLMError as exc:
        logger.error("Ошибка LLM при извлечении маркеров (%s): %s", file.filename, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("Не удалось распарсить ответ LLM (%s): %s", file.filename, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info(
        "Документ обработан: %s (тип=%s, маркеров=%d)",
        file.filename,
        "image" if ext in IMAGE_EXTS else ("pdf" if ext == "pdf" else "docx"),
        len(parsed.get("markers", [])),
    )
    audit.log_document(file.filename, len(parsed.get("markers", [])))

    parsed["markers"] = validation.annotate_markers(parsed.get("markers", []))

    return {
        "filename": file.filename,
        "type": "image" if ext in IMAGE_EXTS else ("pdf" if ext == "pdf" else "docx"),
        "text": text[:2000],
        **parsed,
    }
