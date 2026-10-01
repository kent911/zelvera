# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import httpx

from app.services import i18n, settings_store

from .llm import LLMError, _keep_alive


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await _embed_ollama(texts)


async def _embed_ollama(texts: list[str]) -> list[list[float]]:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("embed_model")
    url = f"{base_url}/api/embed"
    payload = {
        "model": model,
        "input": texts,
        "keep_alive": await _keep_alive(),
    }
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
