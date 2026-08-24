# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from app.services import audit, database, i18n
from app.services.logger import logger
from app.services.pdf_export import export_notes_pdf

router = APIRouter()


class NoteIn(BaseModel):
    article_id: int | None = None
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def _clean_content(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return ""


@router.post("/notes")
def create_note(note: NoteIn) -> dict[str, Any]:
    if not note.content:
        raise HTTPException(status_code=400, detail=i18n.t("note.empty"))
    if note.article_id is not None:
        try:
            database.get_article(note.article_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=i18n.t("article.not_found")) from exc
    result = database.create_note(note.article_id, note.content)
    logger.info("Заметка сохранена: id=%s article_id=%s", result["id"], result["article_id"])
    audit.log_action(
        "note_create",
        f"id={result['id']}, статья={result['article_id'] or 'без привязки'}",
    )
    return result


@router.get("/notes")
def list_notes() -> list[dict[str, Any]]:
    return database.list_notes()


@router.get("/notes/export.pdf")
def export_notes_pdf_route() -> Response:
    notes = database.list_notes()
    payload = export_notes_pdf(notes)
    audit.log_action("note_export", f"заметок: {len(notes)}")
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="notes.pdf"',
        },
    )


@router.delete("/notes/{note_id}")
def delete_note(note_id: int) -> dict[str, bool]:
    if not database.delete_note(note_id):
        raise HTTPException(status_code=404, detail=i18n.t("note.not_found"))
    audit.log_action("note_delete", f"id={note_id}")
    return {"ok": True}
