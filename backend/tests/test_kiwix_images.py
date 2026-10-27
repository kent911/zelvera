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


def test_rank_heart_over_film_and_generic_anatomy():
    results = [
        {
            "title": "The Heart of Humanity",
            "href": "/A/The_Heart_of_Humanity",
            "snippet": "1918 American silent film",
        },
        {"title": "Anatomy", "href": "/A/Anatomy", "snippet": "fish and frog diagrams"},
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    primary = kiwix.pick_primary_article(results, "human heart")
    assert primary is not None
    assert primary["title"] == "Heart"


def test_rank_heart_over_novel():
    results = [
        {
            "title": "Any Human Heart",
            "href": "/A/Any_Human_Heart",
            "snippet": "2002 novel by William Boyd",
        },
        {
            "title": "Anatomy of the human heart",
            "href": "/A/Anatomy_of_the_human_heart",
            "snippet": "chambers and valves",
        },
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    primary = kiwix.pick_primary_article(results, "human heart")
    assert primary is not None
    assert primary["title"] == "Heart"
    picked = kiwix.pick_relevant_images(
        [
            {
                "zim": "z",
                "path": "/I/Any_Human_Heart_cover.jpg",
                "alt": "First edition book cover",
            }
        ],
        "heart",
        "Any Human Heart",
        2,
    )
    assert picked == []


def test_rank_heart_over_radio_station():
    results = [
        {"title": "Heart UK", "href": "/A/Heart_UK", "snippet": "British radio station"},
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    primary = kiwix.pick_primary_article(results, "Heart")
    assert primary is not None
    assert primary["title"] == "Heart"


def test_russian_heart_query_picks_heart_not_lung():
    results = [
        {"title": "Lung", "href": "/A/Lung", "snippet": "respiratory organ"},
        {"title": "Heart UK", "href": "/A/Heart_UK", "snippet": "British radio station"},
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    primary = kiwix.pick_primary_article(results, "покажи сердце человека в разрезе")
    assert primary is not None
    assert primary["title"] == "Heart"


def test_cross_section_query_still_picks_heart():
    results = [
        {"title": "Heart UK", "href": "/A/Heart_UK", "snippet": "British radio station"},
        {"title": "Lung", "href": "/A/Lung", "snippet": "respiratory organ"},
        {"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"},
    ]
    primary = kiwix.pick_primary_article(results, "heart cross section")
    assert primary is not None
    assert primary["title"] == "Heart"


def test_canonical_heart_when_search_misses_article():
    results = [
        {"title": "Heart UK", "href": "/A/Heart_UK", "snippet": "British radio station"},
        {
            "title": "Any Human Heart",
            "href": "/A/Any_Human_Heart",
            "snippet": "2002 novel by William Boyd",
        },
    ]
    primary = kiwix.pick_primary_article(results, "Heart")
    assert primary is not None
    assert primary["title"] == "Heart"
    assert primary["href"] == "/A/Heart"


def test_extract_reads_commons_url():
    html = """
    <img src="//upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Heart_diagram.svg/220px-Heart_diagram.svg.png" alt="Heart">
    """
    extracted = kiwix._extract_images(html, "zim", "/A/Heart", 2)
    assert [p["path"] for p in extracted] == ["/I/Heart_diagram.svg.png"]


def test_extract_reads_content_prefix_and_file_href():
    html = """
    <a href="/content/wikipedia_en_all/I/Heart_diagram.svg">x</a>
    <img src="/wikipedia_en_all/I/e/e5/Diagram_of_the_human_heart.svg" alt="Heart">
    """
    extracted = kiwix._extract_images(html, "wikipedia_en_all", "/A/Heart", 2)
    assert "/I/e/e5/Diagram_of_the_human_heart.svg" in [p["path"] for p in extracted]
    assert "/I/Heart_diagram.svg" in [p["path"] for p in extracted]


def test_image_url_candidates_include_content_and_basename(monkeypatch):
    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix")
    urls = kiwix._image_url_candidates("zim", "/I/e/e5/Heart_diagram.svg")
    paths = [p for p, _ in urls]
    http = [u for _, u in urls]
    assert "/I/e/e5/Heart_diagram.svg" in paths
    assert "/I/Heart_diagram.svg" in paths
    assert any("/content/zim/I/Heart_diagram.svg" in u for u in http)
    assert any("/raw/zim/content/I/Heart_diagram.svg" in u for u in http)


def test_article_path_candidates_include_namespace_variants():
    assert kiwix._article_path_candidates("/A/Heart") == [
        "/A/Heart",
        "/Heart",
        "/A/Heart.html",
        "/Heart.html",
    ]


def test_image_url_candidates_try_svg_without_png_thumb(monkeypatch):
    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix")
    urls = kiwix._image_url_candidates("zim", "/I/Heart_diagram.svg.png")
    paths = [p for p, _ in urls]
    assert "/I/Heart_diagram.svg.png" in paths
    assert "/I/Heart_diagram.svg" in paths


def test_russian_query_searches_english_heart(monkeypatch):
    kiwix.take_pending_images()
    searched: list[str] = []

    async def resolve_zim():
        return "zim"

    async def search(query, _zim):
        searched.append(query)
        return [{"title": "Heart", "href": "/A/Heart", "snippet": "muscular organ"}]

    async def get_article_html(_zim, _href):
        return '<img src="./Heart_diagram.svg" alt="Heart">'

    async def fetch_image(_zim, path):
        return b"img", path

    async def describe(_data, _mime):
        return None

    monkeypatch.setattr(kiwix, "resolve_zim", resolve_zim)
    monkeypatch.setattr(kiwix, "search", search)
    monkeypatch.setattr(kiwix, "get_article_html", get_article_html)
    monkeypatch.setattr(kiwix, "_fetch_image", fetch_image)
    monkeypatch.setattr(kiwix, "_describe_image_bytes", describe)

    out = asyncio.run(kiwix.fetch_tool_results("покажи сердце человека", limit=1))
    pending = kiwix.take_pending_images()

    assert searched == ["heart"]
    assert "[Wikipedia: Heart]" in out
    assert pending
    assert pending[0]["path"].endswith("Heart_diagram.svg")


def test_extract_reads_data_src_and_relative_png():
    html = """
    <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
         data-src="./Diagram_of_the_human_heart.svg.png" alt="Heart">
    """
    extracted = kiwix._extract_images(html, "zim", "/A/Heart", 2)
    assert [p["path"] for p in extracted] == ["/A/Diagram_of_the_human_heart.svg.png"]


def test_pick_skips_generic_anatomy_images():
    candidates = [
        {"zim": "z", "path": "/I/Fish_anatomy.svg", "alt": "Fish anatomy"},
        {"zim": "z", "path": "/I/Frog_dissection.jpg", "alt": "Frog heart labeled"},
    ]
    picked = kiwix.pick_relevant_images(candidates, "heart", "Anatomy", 2)
    assert picked == []


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


def test_pick_keeps_posterior_not_poster():
    candidates = [
        {
            "zim": "z",
            "path": "/I/Blausen_0466_Heart_Posterior.png",
            "alt": "Heart, posterior view",
        },
        {
            "zim": "z",
            "path": "/I/Map_of_the_Human_Heart_poster.jpg",
            "alt": "Theatrical poster",
        },
    ]
    picked = kiwix.pick_relevant_images(candidates, "heart", "Heart", 2)
    assert [p["path"] for p in picked] == ["/I/Blausen_0466_Heart_Posterior.png"]


def test_pick_keeps_infobox_without_query_in_name():
    candidates = [
        {"zim": "z", "path": "/I/Wiki_letter_w.svg", "alt": "icon"},
        {"zim": "z", "path": "/A/_assets_/2010.jpg", "alt": ""},
        {"zim": "z", "path": "/A/_assets_/chambers.svg", "alt": "four chambers"},
    ]
    picked = kiwix.pick_relevant_images(candidates, "сердце в разрезе", "Heart", 2)
    assert [p["path"] for p in picked] == [
        "/A/_assets_/2010.jpg",
        "/A/_assets_/chambers.svg",
    ]


def test_extract_skips_icons_and_reads_srcset():
    html = """
    <img src="../I/Wiki_letter_w.svg" width="20" alt="icon">
    <img src="./_assets_/tiny.png" width="16" alt="">
    <img src="" srcset="./_assets_/Blausen_0466_Heart_Posterior.png 1.5x" alt="">
    <img src="../I/Heart_diagram.svg" alt="Diagram of the human heart">
    """
    extracted = kiwix._extract_images(html, "zim", "/A/Heart", 2)
    assert [p["path"] for p in extracted] == [
        "/A/_assets_/Blausen_0466_Heart_Posterior.png",
        "/I/Heart_diagram.svg",
    ]


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
