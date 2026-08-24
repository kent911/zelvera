# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import base64
from pathlib import Path
from typing import BinaryIO

try:
    import pymupdf as fitz
except ImportError:  # fallback для старых версий PyMuPDF
    import fitz

from docx import Document

from app.services import i18n


class DocumentError(Exception):
    pass


def _open_docx(stream: BinaryIO) -> Document:
    return Document(stream)


def extract_text_from_pdf(stream: BinaryIO) -> str:
    try:
        doc = fitz.open(stream=stream, filetype="pdf")
    except Exception as exc:
        raise DocumentError(i18n.t("document.pdf_open_failed", err=exc)) from exc
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    text = "\n".join(pages).strip()
    doc.close()
    if not text:
        raise DocumentError(i18n.t("document.pdf_no_text"))
    return text


def extract_text_from_docx(stream: BinaryIO) -> str:
    try:
        doc = _open_docx(stream)
    except Exception as exc:
        raise DocumentError(i18n.t("document.docx_open_failed", err=exc)) from exc
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    # текст внутри таблиц (бланки анализов часто табличные)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    text = "\n".join(paragraphs).strip()
    if not text:
        raise DocumentError(i18n.t("document.docx_no_text"))
    return text


def encode_image_bytes(stream: BinaryIO) -> str:
    data = stream.read()
    return base64.b64encode(data).decode("ascii")


def guess_ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def chunk_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    """Делит текст на перекрывающиеся фрагменты по границам слов."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            space = text.rfind(" ", start, end)
            if space > start + size // 2:
                end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks
