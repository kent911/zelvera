# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import norms


def test_known_marker_normal():
    result = norms.check_norm("Гемоглобин", 140, "г/л", "m", 40)
    assert result is not None
    assert result["value"] == 140.0
    assert result["status"] == "normal"


def test_known_marker_high():
    result = norms.check_norm("Гемоглобин", 200, "г/л", "m", 40)
    assert result is not None
    assert result["status"] == "high"


def test_unknown_marker_returns_none():
    assert norms.check_norm("Интерлейкин-6", 7.1, "пг/мл") is None


def test_hemoglobin_differs_by_sex():
    male = norms.check_norm("Гемоглобин", 125, "г/л", "m", 40)
    female = norms.check_norm("Гемоглобин", 125, "г/л", "f", 40)
    assert male is not None and female is not None
    assert male["status"] == "low"
    assert female["status"] == "normal"


def test_check_marker_norm_uses_profile_sex(db, monkeypatch):
    import asyncio

    from app.services import tools

    profile = db.create_profile("Egor", 1985, sex="m")
    monkeypatch.setattr(tools, "_current_profile_id", lambda: profile["id"])
    text = asyncio.run(tools.check_marker_norm("Гемоглобин", 125, "г/л"))
    assert "125" in text
