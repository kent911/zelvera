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
