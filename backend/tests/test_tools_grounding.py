# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio

from app.services import kiwix, settings_store, tools


def _patch_kiwix(monkeypatch, calls):
    monkeypatch.setattr(kiwix, "get_base_url", lambda: "http://kiwix:8080")

    async def resolve_zim():
        return "zim"

    async def search(query, zim, page_length=3):
        calls["search"] += 1
        return [{"title": "Interleukin 6", "href": "/A/IL6", "snippet": "cytokine"}]

    async def article(zim, path):
        return "Interleukin 6 is an inflammatory cytokine."

    monkeypatch.setattr(kiwix, "resolve_zim", resolve_zim)
    monkeypatch.setattr(kiwix, "search", search)
    monkeypatch.setattr(kiwix, "get_article", article)


def _patch_card(monkeypatch, markers):
    monkeypatch.setattr(settings_store, "get_current_profile_id", lambda: 1)
    monkeypatch.setattr(
        tools.database, "list_records", lambda pid=None: [{"id": 1, "created_at": "2026-09-01 10:00"}]
    )
    monkeypatch.setattr(
        tools.database,
        "get_record",
        lambda rid: {"created_at": "2026-09-01 10:00", "markers": markers},
    )


def test_card_grounds_unknown_marker(db, monkeypatch):
    calls = {"search": 0}
    _patch_kiwix(monkeypatch, calls)
    _patch_card(
        monkeypatch,
        [
            {"name": "Интерлейкин-6", "value": 7.1, "unit": "пг/мл"},
            {"name": "Гемоглобин", "value": 140, "unit": "г/л"},
        ],
    )

    out = asyncio.run(tools.get_medical_card())

    assert "Интерлейкин-6" in out
    assert "Справка из офлайн-Википедии" in out
    assert "Interleukin 6" in out
    assert calls["search"] == 1


def test_card_skips_wikipedia_when_all_known(db, monkeypatch):
    calls = {"search": 0}
    _patch_kiwix(monkeypatch, calls)
    _patch_card(
        monkeypatch, [{"name": "Гемоглобин", "value": 140, "unit": "г/л"}]
    )

    out = asyncio.run(tools.get_medical_card())

    assert "Справка из офлайн-Википедии" not in out
    assert calls["search"] == 0


def test_norm_check_grounds_unknown_marker(db, monkeypatch):
    calls = {"search": 0}
    _patch_kiwix(monkeypatch, calls)

    out = asyncio.run(tools.check_marker_norm("Интерлейкин-6", 7.1, "пг/мл"))

    assert "нет показателя" in out
    assert "Interleukin 6" in out
