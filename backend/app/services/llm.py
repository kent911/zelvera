# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json
import logging
import time
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.services import i18n, settings_store

log = logging.getLogger("llm")

SystemMessage = dict
UserMessage = dict
ChatMessage = dict


def _log_ollama_metrics(model: str, phase: str, data: dict | None, seconds: float) -> None:
    prompt = out = 0
    rate = ""
    if isinstance(data, dict):
        try:
            prompt = int(data.get("prompt_eval_count") or 0)
        except (TypeError, ValueError):
            prompt = 0
        try:
            out = int(data.get("eval_count") or 0)
        except (TypeError, ValueError):
            out = 0
        try:
            ev = int(data.get("eval_duration") or 0)
            if ev > 0:
                rate = " ({:.1f} tok/s)".format(out / (ev / 1e9))
        except (TypeError, ValueError):
            pass
    log.info(
        "[metrics] %s model=%s prompt=%d eval=%d%s time=%.1fs",
        phase, model, prompt, out, rate, seconds,
    )


def _log_openai_metrics(model: str, phase: str, usage, seconds: float) -> None:
    prompt = out = 0
    if usage is not None:
        try:
            prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        except (TypeError, ValueError):
            prompt = 0
        try:
            out = int(getattr(usage, "completion_tokens", 0) or 0)
        except (TypeError, ValueError):
            out = 0
    log.info(
        "[metrics] %s model=%s prompt=%d eval=%d time=%.1fs",
        phase, model, prompt, out, seconds,
    )


async def stream_chat(messages: list[ChatMessage]) -> AsyncIterator[str]:
    if settings.llm_backend == "openai":
        async for chunk in _stream_openai(messages):
            yield chunk
    else:
        async for chunk in _stream_ollama(messages):
            yield chunk


MAX_TOOL_ROUNDS = 6


async def chat_with_tools(
    messages: list[ChatMessage],
    tools: list[dict],
    tool_executor,
) -> AsyncIterator[str]:
    """Диалог с поддержкой вызова инструментов (function calling).

    Пока модель вызывает инструменты — сервер исполняет их и возвращает
    результат в беседу. Когда модель даёт финальный текстовый ответ —
    он стримится наружу.
    """
    history: list[ChatMessage] = [dict(m) for m in messages]
    for _ in range(MAX_TOOL_ROUNDS):
        if settings.llm_backend == "openai":
            content, tool_calls = await _complete_with_tools_openai(history, tools)
        else:
            content, tool_calls = await _complete_with_tools_ollama(history, tools)

        if not tool_calls:
            if content:
                yield content
            return

        history.append(_assistant_tool_message(content, tool_calls))
        for call in tool_calls:
            name = call.get("name", "")
            arguments = call.get("arguments", {})
            try:
                result = await tool_executor(name, arguments)
            except Exception as exc:
                result = i18n.t("llm.tool_exec_error", name=name, err=exc)
            history.append(_tool_result_message(call, result))

    yield _error_message(i18n.t("llm.tool_round_limit"))


def _assistant_tool_message(content: str, tool_calls: list[dict]) -> ChatMessage:
    if settings.llm_backend == "openai":
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {
                    "id": c.get("id") or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                    },
                }
                for i, c in enumerate(tool_calls)
            ],
        }
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "function": {
                    "name": c["name"],
                    "arguments": c.get("arguments", {}),
                }
            }
            for c in tool_calls
        ],
    }


def _tool_result_message(tool_call: dict, result: str) -> ChatMessage:
    if settings.llm_backend == "openai":
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id") or "",
            "content": result,
        }
    return {"role": "tool", "content": result}


async def _complete_with_tools_openai(
    messages: list[ChatMessage], tools: list[dict]
) -> tuple[str, list[dict]]:
    if not settings.user_llm_api_key:
        raise LLMError(i18n.t("llm.no_api_key"))
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    t0 = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=settings.user_llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as exc:
        raise LLMError(i18n.t("llm.tools_api_error", err=exc)) from exc
    _log_openai_metrics(
        settings.user_llm_model, "openai_tools_round", resp.usage, time.monotonic() - t0
    )
    msg = resp.choices[0].message
    content = (msg.content or "").strip()
    calls: list[dict] = []
    for tc in msg.tool_calls or []:
        try:
            arguments = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        calls.append(
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": arguments,
            }
        )
    return content, calls


async def _complete_with_tools_ollama(
    messages: list[ChatMessage], tools: list[dict]
) -> tuple[str, list[dict]]:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("chat_model")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "options": {"num_ctx": await _num_ctx()},
    }
    async with httpx.AsyncClient(timeout=300) as client:
        t0 = time.monotonic()
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                detail = exc.response.text[:500]
            logging.getLogger("llm").warning(
                "Ollama chat (tools) ошибка: %s %s", url, detail or exc
            )
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=exc)
            ) from exc
    _log_ollama_metrics(model, "ollama_tools_round", data, time.monotonic() - t0)
    msg = data.get("message", {})
    content = (msg.get("content") or "").strip()
    calls: list[dict] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        arguments = fn.get("arguments") or {}
        calls.append({"name": name, "arguments": arguments})
    return content, calls


async def complete(messages: list[ChatMessage]) -> str:
    """Не-стриминговый вызов: возвращает полный ответ строкой."""
    if settings.llm_backend == "openai":
        return await _complete_openai(messages)
    return await _complete_ollama(messages)


async def ocr_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """Распознавание текста с изображения через vision-модель."""
    if settings.llm_backend == "openai":
        return await _ocr_openai(image_b64, mime_type)
    return await _ocr_ollama(image_b64)


async def describe_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """Описание изображения через vision-модель (для картинок Википедии)."""
    if settings.llm_backend == "openai":
        return await _describe_openai(image_b64, mime_type)
    return await _describe_ollama(image_b64)


async def _num_ctx() -> int:
    raw = settings_store.get("num_ctx")
    try:
        return max(2048, int(raw))
    except (TypeError, ValueError):
        return 32768


async def _vision_max_tokens() -> int | None:
    """Лимит токенов для описания картинок (не для OCR).

    0 или нечисловое значение — без лимита (None).
    """
    try:
        value = int(settings_store.get("vision_max_tokens"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


async def _describe_ollama(image_b64: str) -> str:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("vision_model")
    url = f"{base_url}/api/chat"
    options: dict = {"num_ctx": await _num_ctx()}
    max_tokens = await _vision_max_tokens()
    if max_tokens:
        options["num_predict"] = max_tokens
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": i18n.t("image_prompt"), "images": [image_b64]}
        ],
        "stream": False,
        "options": options,
    }
    async with httpx.AsyncClient(timeout=900) as client:
        t0 = time.monotonic()
        try:
            resp = await client.post(url, json=payload)
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=exc)
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMError(
                i18n.t("llm.ollama_not_json", model=model, status=resp.status_code)
            ) from exc
    if resp.status_code != 200:
        detail = data.get("error") or i18n.t("llm.no_data")
        raise LLMError(
            i18n.t("llm.ollama_error", model=model, status=resp.status_code, detail=detail)
        )
    _log_ollama_metrics(model, "ollama_vision", data, time.monotonic() - t0)
    return data.get("message", {}).get("content", "").strip()


async def _ocr_ollama(image_b64: str) -> str:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("vision_model")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": i18n.t("vision_prompt"), "images": [image_b64]}
        ],
        "stream": False,
        "options": {"num_ctx": await _num_ctx()},
    }
    async with httpx.AsyncClient(timeout=900) as client:
        t0 = time.monotonic()
        try:
            resp = await client.post(url, json=payload)
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=exc)
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMError(
                i18n.t("llm.ollama_not_json", model=model, status=resp.status_code)
            ) from exc
    if resp.status_code != 200:
        detail = data.get("error") or i18n.t("llm.no_data")
        raise LLMError(
            i18n.t("llm.ollama_error", model=model, status=resp.status_code, detail=detail)
        )
    _log_ollama_metrics(model, "ollama_ocr", data, time.monotonic() - t0)
    return data.get("message", {}).get("content", "").strip()


async def _describe_openai(image_b64: str, mime_type: str) -> str:
    if not settings.user_llm_api_key:
        raise LLMError(i18n.t("llm.no_api_key"))
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": i18n.t("image_prompt")},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        raise LLMError(i18n.t("llm.vision_api_error", err=exc)) from exc


async def _ocr_openai(image_b64: str, mime_type: str) -> str:
    if not settings.user_llm_api_key:
        raise LLMError(i18n.t("llm.no_api_key"))
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": i18n.t("vision_prompt")},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        raise LLMError(i18n.t("llm.vision_api_error", err=exc)) from exc


async def _complete_ollama(messages: list[ChatMessage]) -> str:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("chat_model")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": await _num_ctx()},
    }
    async with httpx.AsyncClient(timeout=300) as client:
        t0 = time.monotonic()
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=exc)
            ) from exc
    _log_ollama_metrics(model, "ollama_chat", data, time.monotonic() - t0)
    return data.get("message", {}).get("content", "").strip()


async def _complete_openai(messages: list[ChatMessage]) -> str:
    if not settings.user_llm_api_key:
        raise LLMError(i18n.t("llm.no_api_key"))
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.user_llm_model,
            messages=messages,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        raise LLMError(i18n.t("llm.api_error", err=exc)) from exc


async def _stream_ollama(messages: list[ChatMessage]) -> AsyncIterator[str]:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("chat_model")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"num_ctx": await _num_ctx()},
    }
    t0 = time.monotonic()
    done_data: dict | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
        try:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode("utf-8", "ignore")[:500]
                    log.warning("Ollama stream ошибка: %s %s", url, detail)
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        done_data = data
                        break
        except httpx.HTTPError as exc:
            yield _error_message(i18n.t("llm.ollama_connect_failed", url=url, err=exc))
    _log_ollama_metrics(model, "ollama_stream", done_data, time.monotonic() - t0)


async def _stream_openai(messages: list[ChatMessage]) -> AsyncIterator[str]:
    if not settings.user_llm_api_key:
        yield _error_message(i18n.t("llm.no_api_key"))
        return
    client = AsyncOpenAI(
        base_url=settings.user_llm_base_url,
        api_key=settings.user_llm_api_key,
    )
    try:
        stream = await client.chat.completions.create(
            model=settings.user_llm_model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as exc:
        yield _error_message(i18n.t("llm.openai_api_error", err=exc))


def _error_message(text: str) -> str:
    return f"\n\n{i18n.t('error.prefix')} {text}"


class LLMError(Exception):
    pass
