# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import compare


def _rec(rid, created, markers):
    return {
        "id": rid,
        "created_at": created,
        "source_name": "manual",
        "markers": markers,
    }


def test_compare_tracks_changes_and_status():
    a = _rec(
        1,
        "2026-01-01",
        [
            {"name": "HGB", "value": 140, "unit": "г/л", "status": "normal"},
            {"name": "Глюкоза", "value": 5.0, "unit": "ммоль/л", "status": "normal"},
            {"name": "Ферритин", "value": 80, "unit": "нг/мл", "status": "normal"},
        ],
    )
    b = _rec(
        2,
        "2026-06-01",
        [
            {"name": "Гемоглобин", "value": 150, "unit": "г/л", "status": "normal"},
            {"name": "Глюкоза", "value": 5.0, "unit": "ммоль/л", "status": "normal"},
            {"name": "СОЭ", "value": 12, "unit": "мм/ч", "status": "normal"},
        ],
    )

    result = compare.build_comparison(a, b)
    rows = {r["name"]: r for r in result["markers"]}

    assert result["a"]["id"] == 1 and result["b"]["id"] == 2
    assert rows["Гемоглобин"]["change"] == "up"
    assert rows["Гемоглобин"]["delta"] == 10
    assert rows["Гемоглобин"]["value_a"] == 140  # HGB сопоставлен с Гемоглобином
    assert rows["Глюкоза"]["change"] == "stable"
    assert rows["СОЭ (ESR)"]["change"] == "appeared"
    assert rows["Ферритин"]["change"] == "disappeared"
    assert result["summary"]["appeared"] == 1
    assert result["summary"]["disappeared"] == 1
    assert result["summary"]["total"] == 4


def test_compare_non_numeric_is_unknown():
    a = _rec(1, "2026-01-01", [{"name": "Белок", "value": None, "value_raw": "следы"}])
    b = _rec(2, "2026-02-01", [{"name": "Белок", "value": None, "value_raw": "следы"}])

    result = compare.build_comparison(a, b)
    assert result["markers"][0]["change"] == "unknown"
    assert result["markers"][0]["value_a"] == "следы"


def test_compare_endpoint_with_stored_records(db):
    from app.routes import records

    first = db.create_record(
        source_name="lab",
        summary="",
        markers=[{"name": "HGB", "value": 140, "unit": "г/л", "status": "normal"}],
        date="2026-01-01",
    )
    second = db.create_record(
        source_name="lab",
        summary="",
        markers=[{"name": "Гемоглобин", "value": 150, "unit": "г/л", "status": "normal"}],
        date="2026-06-01",
    )

    result = records.compare_records(first["id"], second["id"])

    assert result["markers"][0]["name"] == "Гемоглобин"
    assert result["markers"][0]["change"] == "up"


def test_trend_ref_corridor(db):
    db.create_record(
        source_name="lab",
        summary="",
        markers=[
            {
                "name": "HGB",
                "value": 140,
                "unit": "г/л",
                "reference_range": "120-160",
                "status": "normal",
            }
        ],
        date="2026-01-01",
    )
    db.create_record(
        source_name="lab",
        summary="",
        markers=[
            {
                "name": "Гемоглобин",
                "value": 150,
                "unit": "г/л",
                "reference_range": "120-160",
                "status": "normal",
            }
        ],
        date="2026-06-01",
    )

    trends = db.marker_trends()
    assert len(trends) == 1
    assert trends[0]["name"] == "Гемоглобин"
    assert trends[0]["ref_low"] == 120
    assert trends[0]["ref_high"] == 160
    assert trends[0]["count"] == 2
