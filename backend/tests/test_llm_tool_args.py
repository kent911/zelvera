# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Разбор вызовов инструментов Ollama.

Ollama может вернуть `arguments` как строку JSON (как OpenAI) либо словарём.
Оба варианта должны превращаться в dict для tool_executor.
"""
import asyncio

from app.services import llm, settings_store


class _FakeResponse:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data, **_kwargs):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def post(self, *_args, **_kwargs):
        return _FakeResponse(self._data)


def _run_tool_calls(monkeypatch, tool_calls):
    data = {"message": {"content": "", "tool_calls": tool_calls}}
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: _FakeClient(data, **kw))
    monkeypatch.setattr(settings_store, "get", lambda _key, default=None: "x")
    return asyncio.run(
        llm._complete_with_tools_ollama([{"role": "user", "content": "hi"}], [])
    )


def test_ollama_string_arguments_parsed_to_dict(monkeypatch):
    _, calls = _run_tool_calls(
        monkeypatch,
        [{"function": {"name": "get_medical_card", "arguments": '{"days": 30}'}}],
    )
    assert calls == [{"name": "get_medical_card", "arguments": {"days": 30}}]


def test_ollama_dict_arguments_pass_through(monkeypatch):
    _, calls = _run_tool_calls(
        monkeypatch,
        [{"function": {"name": "search_articles", "arguments": {"q": "статины"}}}],
    )
    assert calls == [{"name": "search_articles", "arguments": {"q": "статины"}}]


def test_ollama_invalid_string_arguments_become_empty_dict(monkeypatch):
    _, calls = _run_tool_calls(
        monkeypatch,
        [{"function": {"name": "get_medical_card", "arguments": "not json"}}],
    )
    assert calls == [{"name": "get_medical_card", "arguments": {}}]
