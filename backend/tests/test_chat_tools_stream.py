# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Стриминг chat_with_tools: статусы тулов и токены финального ответа."""
import asyncio

from app.services import llm, settings_store


class _StreamResp:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def raise_for_status(self):
        return None

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamClient:
    def __init__(self, lines, **_kwargs):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def stream(self, *_args, **_kwargs):
        return _StreamResp(self._lines)


async def _collect(messages, tools, executor):
    out = []
    async for item in llm.chat_with_tools(messages, tools, executor):
        out.append(item)
    return out


def test_final_answer_streams_tokens_after_thinking(monkeypatch):
    async def fake_round(_messages, _tools):
        yield ("content", "Привет")
        yield ("content", ", мир")

    monkeypatch.setattr(llm, "_iter_tools_round", fake_round)

    async def executor(_name, _args):
        raise AssertionError("tools should not run")

    items = asyncio.run(_collect([{"role": "user", "content": "hi"}], [], executor))
    assert items[0] == {"status": "thinking"}
    assert items[1:] == ["Привет", ", мир"]


def test_tool_round_emits_status_then_streams_answer(monkeypatch):
    rounds = {"n": 0}

    async def fake_round(_messages, _tools):
        rounds["n"] += 1
        if rounds["n"] == 1:
            yield (
                "tool_calls",
                [{"name": "get_medical_card", "arguments": {"days": 30}}],
            )
            return
        yield ("content", "Холестерин в норме")

    monkeypatch.setattr(llm, "_iter_tools_round", fake_round)

    seen = []

    async def executor(name, arguments):
        seen.append((name, arguments))
        return "card"

    items = asyncio.run(_collect([{"role": "user", "content": "холестерин?"}], [], executor))
    assert seen == [("get_medical_card", {"days": 30})]
    assert items == [
        {"status": "thinking"},
        {"status": "get_medical_card"},
        {"status": "thinking"},
        "Холестерин в норме",
    ]


def test_tool_executor_error_is_string_not_raised(monkeypatch):
    rounds = {"n": 0}

    async def fake_round(_messages, _tools):
        rounds["n"] += 1
        if rounds["n"] == 1:
            yield ("tool_calls", [{"name": "get_profile", "arguments": {}}])
            return
        yield ("content", "ок")

    monkeypatch.setattr(llm, "_iter_tools_round", fake_round)

    async def executor(_name, _args):
        raise RuntimeError("boom")

    items = asyncio.run(_collect([{"role": "user", "content": "я?"}], [], executor))
    assert {"status": "get_profile"} in items
    assert items[-1] == "ок"


def test_telegram_skips_status_dicts():
    chunks = [
        {"status": "thinking"},
        {"status": "get_medical_card"},
        "текст",
        {"status": "thinking"},
        " ответа",
    ]
    result = ""
    for chunk in chunks:
        if isinstance(chunk, str):
            result += chunk
    assert result == "текст ответа"


def _run_ollama_stream(monkeypatch, lines):
    monkeypatch.setattr(
        llm.httpx, "AsyncClient", lambda **kw: _StreamClient(lines, **kw)
    )
    monkeypatch.setattr(settings_store, "get", lambda _key, default=None: "x")

    async def run():
        out = []
        async for item in llm._stream_tools_ollama(
            [{"role": "user", "content": "hi"}], []
        ):
            out.append(item)
        return out

    return asyncio.run(run())


def test_stream_tools_ollama_parses_string_arguments(monkeypatch):
    lines = [
        '{"message":{"content":"","tool_calls":[{"function":{"name":"get_medical_card","arguments":"{\\"days\\": 30}"}}]}}',
        '{"message":{"content":""},"done":true}',
    ]
    out = _run_ollama_stream(monkeypatch, lines)
    assert out == [
        ("tool_calls", [{"name": "get_medical_card", "arguments": {"days": 30}}])
    ]


def test_stream_tools_ollama_streams_content(monkeypatch):
    lines = [
        '{"message":{"content":"Hello"}}',
        '{"message":{"content":" world"},"done":true}',
    ]
    out = _run_ollama_stream(monkeypatch, lines)
    assert out == [("content", "Hello"), ("content", " world")]


def _isolate_chat(tmp_path, monkeypatch):
    from app.services import auth, database
    from app.services.telegram_bot import bot as telegram_bot

    monkeypatch.setattr(auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    auth.reset_cache()
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(telegram_bot, "start", _noop)
    monkeypatch.setattr(telegram_bot, "stop", _noop)


def _chat_client(tmp_path, monkeypatch, fake_tools, fake_rag=None):
    import json

    from fastapi.testclient import TestClient

    from app.main import app
    from app.routes import chat
    from app.services import memory, tools

    _isolate_chat(tmp_path, monkeypatch)
    rag_calls = {"n": 0}

    async def _rag(_query):
        rag_calls["n"] += 1
        if fake_rag is not None:
            return await fake_rag(_query)
        return ""

    monkeypatch.setattr(chat, "_rag_context", _rag)
    monkeypatch.setattr(chat, "chat_with_tools", fake_tools)
    monkeypatch.setattr(tools, "profile_context", lambda: "")
    monkeypatch.setattr(memory, "recall_context", lambda _q: "")
    monkeypatch.setattr(memory, "schedule_ingest", lambda *_a, **_k: None)
    return TestClient(app), rag_calls, json


def test_chat_sse_starts_with_thinking(tmp_path, monkeypatch):
    async def fake_tools(_messages, _tools, _executor):
        yield {"status": "get_medical_card"}
        yield "карта"

    client, rag_calls, json = _chat_client(tmp_path, monkeypatch, fake_tools)
    with client:
        client.post("/api/auth/setup", json={"username": "egor", "password": "secret123"})
        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "привет"}]},
        )
        assert resp.status_code == 200
        events = [
            json.loads(line[5:].strip())
            for line in resp.text.split("\n")
            if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")
        ]
    assert events[0] == {"status": "thinking"}
    assert {"status": "get_medical_card"} in events
    assert rag_calls["n"] == 0


def test_chat_rag_only_for_article_query(tmp_path, monkeypatch):
    async def fake_tools(messages, _tools, _executor):
        yield "ответ"

    async def fake_rag(_query):
        return "фрагмент статьи"

    client, rag_calls, _json = _chat_client(
        tmp_path, monkeypatch, fake_tools, fake_rag=fake_rag
    )
    with client:
        client.post("/api/auth/setup", json={"username": "egor", "password": "secret123"})
        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "найди в статьях про витамин D"}]},
        )
        assert resp.status_code == 200
    assert rag_calls["n"] == 1
