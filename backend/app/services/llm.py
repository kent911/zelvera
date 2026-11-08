# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json
import logging
import time
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.services import i18n, net, settings_store

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


def _use_openai() -> bool:
    return settings_store.llm_backend() == "openai"


def _use_openai_vision() -> bool:
    return settings_store.vision_backend() == "openai"


def _openai_client() -> AsyncOpenAI:
    base_url = settings_store.openai_base_url()
    # llama-server в локальной сети: без прокси из окружения (он нужен только Telegram/GitHub).
    http_client = httpx.AsyncClient(**net.client_options(base_url)) if net.is_lan_url(base_url) else None
    return AsyncOpenAI(
        base_url=base_url,
        api_key=settings_store.openai_api_key(),
        http_client=http_client,
    )


def _openai_chat_model() -> str:
    return settings_store.get("chat_model") or settings.user_llm_model


def _openai_vision_model() -> str:
    return settings_store.get("vision_model") or settings.user_llm_vision_model


def coalesce_system_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    """llama-server / bonsai2: system может быть только первым сообщением."""
    systems: list[str] = []
    rest: list[ChatMessage] = []
    for msg in messages:
        if (msg.get("role") or "").strip() == "system":
            content = (msg.get("content") or "").strip()
            if content:
                systems.append(content)
            continue
        rest.append(msg)
    if not systems:
        return rest
    return [{"role": "system", "content": "\n\n".join(systems)}, *rest]


async def stream_chat(messages: list[ChatMessage]) -> AsyncIterator[str]:
    if _use_openai():
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
) -> AsyncIterator[str | dict]:
    """Диалог с поддержкой вызова инструментов (function calling).

    Сначала наружу уходит статус (thinking / имя тула). Пока модель
    вызывает инструменты — сервер исполняет их. Финальный текст
    стримится токенами.
    """
    history: list[ChatMessage] = [dict(m) for m in messages]
    yield {"status": "thinking"}
    for _ in range(MAX_TOOL_ROUNDS):
        content = ""
        tool_calls: list[dict] = []
        async for kind, payload in _iter_tools_round(history, tools):
            if kind == "tool_calls":
                tool_calls = payload
            elif kind == "content":
                content += payload
                if not tool_calls:
                    yield payload

        if not tool_calls:
            return

        history.append(_assistant_tool_message(content, tool_calls))
        for call in tool_calls:
            name = call.get("name", "")
            arguments = call.get("arguments", {})
            if name:
                yield {"status": name}
            try:
                result = await tool_executor(name, arguments)
            except Exception as extra:
                result = i18n.t("llm.tool_exec_error", name=name, err=extra)
            history.append(_tool_result_message(call, result))
        yield {"status": "thinking"}

    yield _error_message(i18n.t("llm.tool_round_limit"))


async def _iter_tools_round(
    messages: list[ChatMessage], tools: list[dict]
) -> AsyncIterator[tuple[str, object]]:
    if _use_openai():
        async for item in _stream_tools_openai(messages, tools):
            yield item
    else:
        async for item in _stream_tools_ollama(messages, tools):
            yield item


def _assistant_tool_message(content: str, tool_calls: list[dict]) -> ChatMessage:
    if _use_openai():
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
    if _use_openai():
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id") or "",
            "content": result,
        }
    return {"role": "tool", "content": result}


async def _complete_with_tools_openai(
    messages: list[ChatMessage], tools: list[dict]
) -> tuple[str, list[dict]]:
    model = _openai_chat_model()
    client = _openai_client()
    t0 = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=coalesce_system_messages(messages),
            tools=tools,
            tool_choice="auto",
        )
    except Exception as exc:
        raise LLMError(i18n.t("llm.tools_api_error", err=exc)) from exc
    _log_openai_metrics(
        model, "openai_tools_round", resp.usage, time.monotonic() - t0
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
        "keep_alive": await _keep_alive(),
        "options": {"num_ctx": await _num_ctx()},
    }
    async with net.async_client(url, timeout=300) as client:
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
    calls = [
        _normalize_ollama_tool_call(tc) for tc in msg.get("tool_calls") or []
    ]
    return content, calls


def _normalize_ollama_tool_call(tc: dict) -> dict:
    fn = tc.get("function", {})
    name = fn.get("name", "")
    arguments = fn.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return {"name": name, "arguments": arguments}


async def _stream_tools_openai(
    messages: list[ChatMessage], tools: list[dict]
) -> AsyncIterator[tuple[str, object]]:
    model = _openai_chat_model()
    client = _openai_client()
    t0 = time.monotonic()
    usage = None
    buckets: dict[int, dict] = {}
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=coalesce_system_messages(messages),
            tools=tools,
            tool_choice="auto",
            stream=True,
        )
        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            for tc in delta.tool_calls or []:
                idx = tc.index if tc.index is not None else 0
                bucket = buckets.setdefault(
                    idx, {"id": "", "name": "", "arguments": ""}
                )
                if tc.id:
                    bucket["id"] = tc.id
                fn = tc.function
                if fn is None:
                    continue
                if fn.name:
                    bucket["name"] += fn.name
                if fn.arguments:
                    bucket["arguments"] += fn.arguments
            if delta.content and not buckets:
                yield ("content", delta.content)
    except Exception as exc:
        raise LLMError(i18n.t("llm.tools_api_error", err=exc)) from exc
    _log_openai_metrics(
        model, "openai_tools_stream", usage, time.monotonic() - t0
    )
    if not buckets:
        return
    calls: list[dict] = []
    for idx in sorted(buckets):
        bucket = buckets[idx]
        try:
            arguments = json.loads(bucket["arguments"] or "{}")
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append(
            {
                "id": bucket["id"],
                "name": bucket["name"],
                "arguments": arguments,
            }
        )
    yield ("tool_calls", calls)


async def _stream_tools_ollama(
    messages: list[ChatMessage], tools: list[dict]
) -> AsyncIterator[tuple[str, object]]:
    base_url = settings_store.get("ollama_base_url")
    model = settings_store.get("chat_model")
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": True,
        "keep_alive": await _keep_alive(),
        "options": {"num_ctx": await _num_ctx()},
    }
    t0 = time.monotonic()
    done_data: dict | None = None
    calls: list[dict] = []
    async with net.async_client(url, timeout=httpx.Timeout(300, connect=10)) as client:
        try:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode("utf-8", "ignore")[:500]
                    log.warning(
                        "Ollama chat (tools stream) ошибка: %s %s", url, detail
                    )
                    resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("message") or {}
                    chunk_calls = msg.get("tool_calls") or []
                    if chunk_calls:
                        calls = [
                            _normalize_ollama_tool_call(tc) for tc in chunk_calls
                        ]
                    chunk = msg.get("content") or ""
                    if chunk and not chunk_calls:
                        yield ("content", chunk)
                    if data.get("done"):
                        done_data = data
                        break
        except httpx.HTTPError as extra:
            log.warning(
                "Ollama chat (tools stream) ошибка: %s %s", url, extra
            )
            raise LLMError(
                i18n.t("llm.ollama_connect_failed", url=url, err=extra)
            ) from extra
    _log_ollama_metrics(
        model, "ollama_tools_stream", done_data, time.monotonic() - t0
    )
    if calls:
        yield ("tool_calls", calls)


async def complete(messages: list[ChatMessage]) -> str:
    """Не-стриминговый вызов: возвращает полный ответ строкой."""
    if _use_openai():
        return await _complete_openai(messages)
    return await _complete_ollama(messages)


def _openai_image_unsupported(exc: Exception) -> bool:
    text = str(exc).lower()
    return "image input is not supported" in text or "mmproj" in text


async def ocr_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """Распознавание текста с изображения.

    Движок выбран отдельно (vision_backend); llama-server без mmproj
    картинки не читает — тогда OCR идёт в Ollama.
    """
    if _use_openai_vision():
        try:
            return await _ocr_openai(image_b64, mime_type)
        except LLMError as exc:
            if not _openai_image_unsupported(exc):
                raise
            log.warning("llama-server без vision, OCR через Ollama: %s", exc)
    return await _ocr_ollama(image_b64)


async def describe_image(image_b64: str, mime_type: str = "image/jpeg") -> str:
    """Описание изображения (картинки Википедии). Движок — vision_backend."""
    if _use_openai_vision():
        try:
            return await _describe_openai(image_b64, mime_type)
        except LLMError as exc:
            if not _openai_image_unsupported(exc):
                raise
            log.warning("llama-server без vision, описание через Ollama: %s", exc)
    return await _describe_ollama(image_b64)


async def _num_ctx() -> int:
    raw = settings_store.get("num_ctx")
    try:
        return max(2048, int(raw))
    except (TypeError, ValueError):
        return 32768


async def _keep_alive() -> str:
    """Как долго Ollama держит модель в памяти (холодная загрузка 26b ~20 c)."""
    return (settings_store.get("ollama_keep_alive") or "30m").strip() or "30m"


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
        "keep_alive": await _keep_alive(),
        "options": options,
    }
    async with net.async_client(url, timeout=900) as client:
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
        "keep_alive": await _keep_alive(),
        "options": {"num_ctx": await _num_ctx()},
    }
    async with net.async_client(url, timeout=900) as client:
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
    client = _openai_client()
    try:
        resp = await client.chat.completions.create(
            model=_openai_vision_model(),
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
    client = _openai_client()
    try:
        resp = await client.chat.completions.create(
            model=_openai_vision_model(),
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
        "keep_alive": await _keep_alive(),
        "options": {"num_ctx": await _num_ctx()},
    }
    async with net.async_client(url, timeout=300) as client:
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
    client = _openai_client()
    try:
        resp = await client.chat.completions.create(
            model=_openai_chat_model(),
            messages=coalesce_system_messages(messages),
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
        "keep_alive": await _keep_alive(),
        "options": {"num_ctx": await _num_ctx()},
    }
    t0 = time.monotonic()
    done_data: dict | None = None
    async with net.async_client(url, timeout=httpx.Timeout(300, connect=10)) as client:
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
    client = _openai_client()
    try:
        stream = await client.chat.completions.create(
            model=_openai_chat_model(),
            messages=coalesce_system_messages(messages),
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
