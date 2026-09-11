# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import marker_catalog


def test_catalog_has_entries():
    assert len(marker_catalog.list_catalog()) >= 40


def test_synonyms_share_canonical_name():
    names = {
        marker_catalog.canonical_name(n) for n in ("Гемоглобин", "HGB", "Hb", "гемоглобин")
    }
    assert names == {"Гемоглобин"}


def test_synonym_keys_are_unique():
    keys = list(marker_catalog.SYNONYMS)
    assert len(keys) == len(set(keys))


def test_unknown_marker_returns_none():
    assert marker_catalog.canonical_key("Интерлейкин-6") is None
    assert marker_catalog.entry_for("Интерлейкин-6") is None


def test_canonical_name_falls_back_to_input():
    assert marker_catalog.canonical_name("Интерлейкин-6") == "Интерлейкин-6"
