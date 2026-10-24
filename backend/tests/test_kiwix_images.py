# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio

from app.services import kiwix


def test_wikipedia_images_are_numbered(monkeypatch):
    kiwix.take_pending_images()

    async def resolve_zim():
        return "zim"

    async def search(_query, _zim):
        return [{"title": "Heart valve", "href": "/A/Heart_valve", "snippet": "valves"}]

    async def get_article_html(_zim, _href):
        return "<html><body>text</body></html>"

    def extract_images(_html, zim, _href, _max_images):
        return [
            {"zim": zim, "path": "/I/a.jpg", "alt": "four valves"},
            {"zim": zim, "path": "/I/b.jpg", "alt": "prosthetic valve"},
        ]

    async def fetch_image(_zim, path):
        return b"img", path

    async def describe(_data, _mime):
        return None

    monkeypatch.setattr(kiwix, "resolve_zim", resolve_zim)
    monkeypatch.setattr(kiwix, "search", search)
    monkeypatch.setattr(kiwix, "get_article_html", get_article_html)
    monkeypatch.setattr(kiwix, "_extract_images", extract_images)
    monkeypatch.setattr(kiwix, "_fetch_image", fetch_image)
    monkeypatch.setattr(kiwix, "_describe_image_bytes", describe)

    out = asyncio.run(kiwix.fetch_tool_results("heart valve", limit=1))
    pending = kiwix.take_pending_images()

    assert "[Image 1: four valves]" in out
    assert "[Image 2: prosthetic valve]" in out
    assert "[[рис. N]]" in out
    assert [p["index"] for p in pending] == [1, 2]
    assert pending[0]["source"] == "Heart valve"
    assert pending[1]["caption"] == "prosthetic valve"
