# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import i18n, tools


def test_profile_tool_returns_anketa(db, monkeypatch):
    profile = db.create_profile("Egor", 1985, 180, 80.0, "A(II) Rh+")
    monkeypatch.setattr(tools, "_current_profile_id", lambda: profile["id"])

    text = tools.get_profile()
    assert "Egor" in text
    assert "1985" in text
    assert "A(II) Rh+" in text
    assert "180" in text

    context = tools.profile_context()
    assert "Egor" in context
    assert "A(II) Rh+" in context


def test_profile_tool_falls_back_to_first_profile(db, monkeypatch):
    profile = db.create_profile("Fallback", 1990)
    monkeypatch.setattr(tools, "_current_profile_id", lambda: 999999)
    monkeypatch.setattr(db, "list_profiles", lambda: [profile])

    assert "Fallback" in tools.get_profile()


def test_profile_tool_empty(db, monkeypatch):
    monkeypatch.setattr(tools, "_current_profile_id", lambda: None)
    monkeypatch.setattr(db, "list_profiles", lambda: [])
    assert tools.get_profile() == i18n.t("tool.get_profile.empty")
    assert tools.profile_context() == ""
