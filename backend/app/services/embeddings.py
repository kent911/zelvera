# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.services import i18n, settings_store

from .llm import LLMError


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.llm_backend == "openai":
        return await _embed_openai(texts)
    return await _embed_ollama(texts)


async def _embed_ollama(texts: list[str]) -> list[list[float]]:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("embed_model")
    url = f"{base_url}/api/embed"
    payload = {"model": model, "input": texts}
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=exc)
            ) from exc
    embeddings = data.get("embeddings")
    if not embeddings:
        raise LLMError(i18n.t("embeddings.empty"))
    return embeddings


async def _embed_openai(texts: list[str]) -> list[list[float]]:
    if not settings.user_llm_api_key:
        raise LLMError(i18n.t("llm.no_api_key"))
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    try:
        resp = await client.embeddings.create(
            model=settings.user_llm_embed_model,
            input=texts,
        )
    except Exception as exc:
        raise LLMError(i18n.t("embeddings.api_error", err=exc)) from exc
    return [item.embedding for item in resp.data]
