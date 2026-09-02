# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
from io import BytesIO
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services import articles_db, audit, database, document, embeddings, i18n, llm

router = APIRouter()

ARTICLE_EXTS = {"pdf", "docx", "txt"}
MAX_BYTES = 25 * 1024 * 1024

SUMMARY_PART_SIZE = 9000


def _truncate_q(text: str, limit: int = 120) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


async def _summarize_long_text(text: str) -> str:
    """Резюмирует длинный текст по частям, затем объединяет результат."""
    parts = [
        text[i : i + SUMMARY_PART_SIZE]
        for i in range(0, len(text), SUMMARY_PART_SIZE)
    ]
    if not parts:
        return ""
    if len(parts) == 1:
        return await llm.complete(
            [{"role": "user", "content": i18n.t("summary_prompt", text=text[:12000])}]
        )

    partials: list[str] = []
    for part in parts[:10]:
        try:
            summary = await llm.complete(
                [{"role": "user", "content": i18n.t("summary_prompt", text=part)}]
            )
            partials.append(summary.strip())
        except llm.LLMError:
            continue
    if not partials:
        return ""

    try:
        final = await llm.complete(
            [
                {
                    "role": "user",
                    "content": i18n.t("final_summary_prompt", parts="\n\n".join(partials)),
                }
            ]
        )
        return final.strip() or "\n\n".join(partials)
    except llm.LLMError:
        return "\n\n".join(partials)


class SearchQuery(BaseModel):
    query: str
    limit: int = 5


@router.post("/articles")
async def upload_article(file: UploadFile = File(...)) -> dict[str, Any]:
    ext = document.guess_ext(file.filename or "")
    if ext not in ARTICLE_EXTS:
        raise HTTPException(
            status_code=415,
            detail=i18n.t("article.unsupported", exts=", ".join(sorted(ARTICLE_EXTS))),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=i18n.t("article.empty_file"))
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail=i18n.t("article.too_large")
        )

    try:
        if ext == "pdf":
            text = await asyncio.to_thread(
                document.extract_text_from_pdf, BytesIO(content)
            )
        elif ext == "docx":
            text = await asyncio.to_thread(
                document.extract_text_from_docx, BytesIO(content)
            )
        else:
            text = content.decode("utf-8", errors="replace")
    except document.DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if len(text.strip()) < 50:
        raise HTTPException(
            status_code=422, detail=i18n.t("article.too_short")
        )

    chunks = document.chunk_text(text)

    try:
        embeddings_list = await embeddings.embed_texts(chunks)
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        summary = await _summarize_long_text(text)
    except llm.LLMError:
        summary = ""

    article_id = await asyncio.to_thread(database.create_article, file.filename)
    try:
        chunk_count = await asyncio.to_thread(
            articles_db.add_chunks, article_id, file.filename, chunks, embeddings_list
        )
        await asyncio.to_thread(
            database.update_article_summary, article_id, summary, chunk_count
        )
    except Exception:
        await asyncio.to_thread(articles_db.delete_article, article_id)
        await asyncio.to_thread(database.delete_article, article_id)
        raise

    audit.log_action(
        "article_upload",
        f"«{file.filename}» — фрагментов: {chunk_count}",
    )
    return {
        "id": article_id,
        "filename": file.filename,
        "summary": summary,
        "chunk_count": chunk_count,
    }


@router.get("/articles")
async def list_articles() -> list[dict[str, Any]]:
    return await asyncio.to_thread(database.list_articles)


@router.post("/articles/search")
async def search_articles(q: SearchQuery) -> list[dict[str, Any]]:
    if not q.query.strip():
        raise HTTPException(status_code=400, detail=i18n.t("search.empty"))
    try:
        (query_embedding,) = await embeddings.embed_texts([q.query.strip()])
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    audit.log_action("article_search", _truncate_q(q.query))
    return await asyncio.to_thread(
        articles_db.hybrid_query, q.query.strip(), query_embedding, q.limit
    )


@router.post("/articles/{article_id}/search")
async def search_article_chunks(article_id: int, q: SearchQuery) -> list[dict[str, Any]]:
    """Ищет релевантные фрагменты ВНУТРИ конкретной статьи."""
    if not q.query.strip():
        raise HTTPException(status_code=400, detail=i18n.t("search.empty"))
    try:
        (query_embedding,) = await embeddings.embed_texts([q.query.strip()])
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await asyncio.to_thread(
        articles_db.hybrid_query, q.query.strip(), query_embedding, q.limit, article_id
    )


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int) -> dict[str, bool]:
    await asyncio.to_thread(articles_db.delete_article, article_id)
    if not await asyncio.to_thread(database.delete_article, article_id):
        raise HTTPException(status_code=404, detail=i18n.t("article.not_found"))
    audit.log_action("article_delete", f"id={article_id}")
    return {"ok": True}
