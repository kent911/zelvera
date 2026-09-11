# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
import json

from app.services import extractor, kiwix


def _patch_kiwix(monkeypatch):
    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix:8080")

    async def resolve_zim():
        return "zim"

    async def search(query, zim, page_length=3):
        return [{"title": "Interleukin 6", "href": "/A/IL6", "snippet": "cytokine"}]

    async def article(zim, path):
        return "Interleukin 6 is an inflammatory cytokine."

    monkeypatch.setattr(kiwix, "resolve_zim", resolve_zim)
    monkeypatch.setattr(kiwix, "search", search)
    monkeypatch.setattr(kiwix, "get_article", article)


def test_extraction_refines_unknown_marker(db, monkeypatch):
    _patch_kiwix(monkeypatch)
    responses = [
        json.dumps(
            {
                "markers": [{"name": "Интерлейкин-6", "value": 7.1, "unit": "пг/мл"}],
                "summary": "draft",
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "markers": [
                    {"name": "Интерлейкин-6 (IL-6)", "value": 7.1, "unit": "пг/мл"}
                ],
                "summary": "refined",
            },
            ensure_ascii=False,
        ),
    ]
    calls = {"n": 0}

    async def fake_complete(messages):
        calls["n"] += 1
        return responses[min(calls["n"] - 1, len(responses) - 1)]

    monkeypatch.setattr(extractor.llm, "complete", fake_complete)

    result = asyncio.run(extractor.extract_markers("Интерлейкин-6 7.1"))

    assert calls["n"] == 2
    assert result["summary"] == "refined"
    assert result["wiki_sources"][0]["title"] == "Interleukin 6"


def test_extraction_skips_wikipedia_when_all_known(db, monkeypatch):
    calls = {"n": 0, "search": 0}

    async def fake_complete(messages):
        calls["n"] += 1
        return json.dumps(
            {
                "markers": [{"name": "Гемоглобин", "value": 140, "unit": "г/л"}],
                "summary": "ok",
            },
            ensure_ascii=False,
        )

    async def forbidden_search(*args, **kwargs):
        calls["search"] += 1
        raise AssertionError("Wikipedia must not be queried for known markers")

    monkeypatch.setattr(extractor.llm, "complete", fake_complete)
    monkeypatch.setattr(kiwix, "search", forbidden_search)

    result = asyncio.run(extractor.extract_markers("Гемоглобин 140"))

    assert calls["n"] == 1
    assert "wiki_sources" not in result
    assert calls["search"] == 0
