# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio

from app.services import kiwix, wiki_lookup


def test_lookup_and_cache(db, monkeypatch):
    calls = {"search": 0}

    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix:8080")

    async def fake_search(query, zim, page_length=3):
        calls["search"] += 1
        return [{"title": "Interleukin 6", "href": "/A/IL6", "snippet": "cytokine"}]

    async def fake_article(zim, path):
        return "Interleukin 6 is a cytokine."

    monkeypatch.setattr(kiwix, "search", fake_search)
    monkeypatch.setattr(kiwix, "get_article", fake_article)

    first = asyncio.run(wiki_lookup.lookup_marker("Интерлейкин-6", "zim"))
    second = asyncio.run(wiki_lookup.lookup_marker("Интерлейкин-6", "zim"))

    assert first is not None
    assert first["title"] == "Interleukin 6"
    assert first["url"].startswith("http://kiwix:8080/viewer#content/zim")
    assert second == first
    assert calls["search"] == 1


def test_negative_result_is_cached(db, monkeypatch):
    calls = {"search": 0}

    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix:8080")

    async def empty_search(query, zim, page_length=3):
        calls["search"] += 1
        return []

    monkeypatch.setattr(kiwix, "search", empty_search)

    assert asyncio.run(wiki_lookup.lookup_marker("Загадочный-9", "zim")) is None
    assert asyncio.run(wiki_lookup.lookup_marker("Загадочный-9", "zim")) is None
    assert calls["search"] == 1


def test_no_kiwix_returns_none(db, monkeypatch):
    monkeypatch.setattr(kiwix, "get_base_url", lambda: "")
    assert asyncio.run(wiki_lookup.lookup_marker("Интерлейкин-6", "zim")) is None
