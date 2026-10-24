# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import articles_db, audit, embeddings, i18n, kiwix, llm, memory, settings_store, tools
from app.services.llm import chat_with_tools, stream_chat

router = APIRouter()
logger = logging.getLogger("chat")



class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., description="История диалога [{role, content}]")


_ALLOWED_ROLES = {"user", "assistant"}


async def _rag_context(query: str) -> str:
    """Ищет релевантные фрагменты из базы научных статей для контекста чата."""
    if not query.strip():
        return ""
    try:
        (query_embedding,) = await embeddings.embed_texts([query.strip()])
        results = await asyncio.to_thread(
            articles_db.hybrid_query, query.strip(), query_embedding, 12
        )
    except llm.LLMError:
        return ""
    if not results:
        return ""
    parts = [
        f"[Фрагмент из статьи «{r['title']}»]\n{r['chunk']}" for r in results
    ]
    return "\n\n".join(parts)


_ARTICLE_HINTS = (
    "стать",
    "исследован",
    "научн",
    "публикаци",
    "журнал",
    "источник",
    "доклад",
    "исслед",
    "базе статей",
    "что в статьях",
    "найди в статьях",
    "мета-анализ",
    "клиническ",
)


def _looks_like_article_query(text: str) -> bool:
    low = (text or "").lower()
    return any(h in low for h in _ARTICLE_HINTS)


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "backend": settings_store.llm_backend(),
        "model": settings_store.get("chat_model"),
    }


@router.get("/config")
async def config() -> dict:
    llm_status, kiwix_status = await asyncio.gather(
        settings_store.probe_llm(),
        kiwix.check_connection(),
    )
    return {
        "backend": llm_status["backend"],
        "vision_backend": settings_store.vision_backend(),
        "model": llm_status["model"],
        "reachable": llm_status["reachable"],
        "llm_error": llm_status["error"],
        "ollama_url": settings_store.get("ollama_base_url"),
        "openai_url": settings_store.openai_base_url(),
        "kiwix": kiwix_status,
    }


@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    messages: list[dict] = [{"role": "system", "content": i18n.t("chat_system")}]
    messages.extend(
        {
            "role": role,
            "content": str(m.get("content", "")),
        }
        for m in req.messages
        for role in [m.get("role", "user")]
        if role in _ALLOWED_ROLES
    )

    last_user = next(
        (m.get("content", "") for m in reversed(req.messages) if m.get("role") == "user"),
        "",
    )
    audit.log_chat(str(last_user))

    profile_text = tools.profile_context()
    if profile_text:
        messages.insert(1, {"role": "system", "content": profile_text})

    memory_text = memory.recall_context(str(last_user))
    if memory_text:
        messages.insert(1, {"role": "system", "content": memory_text})

    async def event_stream():
        start = time.monotonic()
        rounds = 0
        acc = ""
        pending: list[dict] = []
        try:
            yield _SSE_PAD
            yield _sse({"status": "thinking"})
            if _looks_like_article_query(last_user):
                rag_text = await _rag_context(str(last_user))
                if rag_text:
                    messages.insert(
                        1,
                        {
                            "role": "system",
                            "content": (
                                "Ниже приведены фрагменты из базы научных статей пользователя. "
                                "Используй их ТОЛЬКО если вопрос действительно про научные данные, "
                                "исследования или статьи. Если вопрос про медицинскую карту, анализы "
                                "или показатели пользователя — фрагменты игнорируй и используй "
                                "инструмент get_medical_card. Не выдумывай данные, которых нет "
                                "в фрагментах.\n\n"
                                f"Фрагменты:\n{rag_text}"
                            ),
                        },
                    )
                    yield _sse(
                        "Поискал в вашей базе научных статей — вот что нашлось по вопросу.\n\n"
                    )

            async def tool_executor(name: str, arguments: dict):
                nonlocal rounds
                rounds += 1
                result = await tools.execute_tool(name, arguments)
                for img in kiwix.take_pending_images():
                    if img not in pending:
                        pending.append(img)
                return result

            try:
                async for item in chat_with_tools(
                    messages, tools.get_tools(), tool_executor
                ):
                    if await request.is_disconnected():
                        return
                    if isinstance(item, str):
                        acc += item
                        yield _sse(item)
                    elif isinstance(item, dict) and item.get("status"):
                        if pending:
                            yield _sse(_images_payload(pending))
                        yield _sse({"status": item["status"]})
            except llm.LLMError:
                try:
                    async for chunk in stream_chat(messages):
                        if await request.is_disconnected():
                            return
                        acc += chunk
                        yield _sse(chunk)
                except llm.LLMError as exc:
                    yield _sse(f"{i18n.t('error.prefix')} {exc}")
            except asyncio.CancelledError:
                return
            if pending:
                yield _sse(_images_payload(pending))
            yield "data: [DONE]\n\n"
            if acc.strip() and str(last_user).strip():
                memory.schedule_ingest(str(last_user), acc)
        finally:
            logger.info(
                "[metrics] chat total time=%.1fs tool_rounds=%d images=%d",
                time.monotonic() - start,
                rounds,
                len(pending) if "pending" in locals() else 0,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_SSE_PAD = ":" + (" " * 2048) + "\n\n"


def _images_payload(images: list[dict]) -> dict:
    out = []
    for i, img in enumerate(images, 1):
        item = dict(img)
        item.setdefault("index", i)
        out.append(item)
    return {"images": out}


def _sse(data: str | dict) -> str:
    if isinstance(data, str):
        return f"data: {json.dumps({'content': data}, ensure_ascii=False)}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
