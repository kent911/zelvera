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
    system_prompt: str | None = None


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
    messages: list[dict] = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    else:
        messages.append({"role": "system", "content": i18n.t("chat_system")})
    messages.extend(
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in req.messages
    )

    last_user = next(
        (m.get("content", "") for m in reversed(req.messages) if m.get("role") == "user"),
        "",
    )
    audit.log_chat(str(last_user))
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
        try:
            if rag_text and _looks_like_article_query(last_user):
                yield _sse("Поискал в вашей базе научных статей — вот что нашлось по вопросу.\n\n")

            pending: list[dict] = []

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
            except llm.LLMError:
                async for chunk in stream_chat(messages):
                    if await request.is_disconnected():
                        return
                    acc += chunk
                    yield _sse(chunk)
            except asyncio.CancelledError:
                return
            if pending:
                yield _sse({"images": pending})
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: str | dict) -> str:
    if isinstance(data, str):
        return f"data: {json.dumps({'content': data}, ensure_ascii=False)}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
