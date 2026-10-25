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


def test_rank_prefers_title_match_over_mention():
    results = [
        {"title": "ABO (gene)", "href": "/A/ABO_(gene)", "snippet": "heart of the antigen"},
        {"title": "Heart", "href": "/A/Heart", "snippet": "the human heart"},
        {"title": "Heart (disambiguation)", "href": "/A/Heart_(disambiguation)", "snippet": "heart"},
    ]
    ranked = kiwix.rank_search_results(results, "heart")
    assert ranked[0]["title"] == "Heart"
    assert all(r["title"] != "ABO (gene)" for r in ranked)


def test_rank_skips_film_when_anatomy_exists():
    results = [
        {
            "title": "Map of the Human Heart",
            "href": "/A/Map_of_the_Human_Heart",
            "snippet": "1992 film",
        },
        {
            "title": "Anatomy of the human heart",
            "href": "/A/Anatomy_of_the_human_heart",
            "snippet": "chambers and valves",
        },
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    ranked = kiwix.rank_search_results(results, "human heart")
    assert ranked[0]["title"] in {"Heart", "Anatomy of the human heart"}
    assert ranked[0]["title"] != "Map of the Human Heart"


def test_pick_relevant_images_skips_offtopic():
    candidates = [
        {"zim": "z", "path": "/I/Chromosome_9.png", "alt": "Chromosome 9"},
        {"zim": "z", "path": "/I/ABO_gene.svg", "alt": "ABO gene"},
        {"zim": "z", "path": "/I/Heart_diagram.svg", "alt": "Diagram of the human heart"},
        {"zim": "z", "path": "/I/Wiki_letter_w.svg", "alt": "icon"},
    ]
    picked = kiwix.pick_relevant_images(candidates, "heart", "Heart", 2)
    assert [p["path"] for p in picked] == ["/I/Heart_diagram.svg"]


def test_pick_skips_film_poster():
    candidates = [
        {
            "zim": "z",
            "path": "/I/Map_of_the_Human_Heart_poster.jpg",
            "alt": "Theatrical poster",
        },
        {
            "zim": "z",
            "path": "/I/Heart_diagram.svg",
            "alt": "Diagram of the human heart",
        },
    ]
    picked = kiwix.pick_relevant_images(candidates, "heart", "Heart", 2)
    assert [p["path"] for p in picked] == ["/I/Heart_diagram.svg"]


def test_images_only_from_primary_article(monkeypatch):
    kiwix.take_pending_images()
    fetched_hrefs: list[str] = []

    async def resolve_zim():
        return "zim"

    async def search(_query, _zim):
        return [
            {"title": "ABO (gene)", "href": "/A/ABO_(gene)", "snippet": "heart of the antigen"},
            {"title": "Heart", "href": "/A/Heart", "snippet": "the human heart"},
        ]

    async def get_article_html(_zim, href):
        fetched_hrefs.append(href)
        return "<html><body>text</body></html>"

    def extract_images(_html, zim, href, _max_images):
        if href == "/A/ABO_(gene)":
            return [{"zim": zim, "path": "/I/Chromosome_9.png", "alt": "Chromosome 9"}]
        return [{"zim": zim, "path": "/I/Heart_diagram.svg", "alt": "Diagram of the human heart"}]

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

    out = asyncio.run(kiwix.fetch_tool_results("heart", limit=3))
    pending = kiwix.take_pending_images()

    assert fetched_hrefs == ["/A/Heart"]
    assert "[Wikipedia: Heart]" in out
    assert "Chromosome" not in out
    assert [p["path"] for p in pending] == ["/I/Heart_diagram.svg"]
    assert pending[0]["source"] == "Heart"
