# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import longterm


def _rec(rid, date, markers):
    return {"id": rid, "created_at": date, "markers": markers}


def test_longterm_groups_by_year_and_median():
    records = [
        _rec(1, "2018-03-01", [{"name": "HGB", "value": 120, "unit": "г/л", "reference_range": "120-160"}]),
        _rec(2, "2018-09-01", [{"name": "HGB", "value": 140, "unit": "г/л", "reference_range": "120-160"}]),
        _rec(3, "2020-05-01", [{"name": "HGB", "value": 150, "unit": "г/л", "reference_range": "120-160"}]),
    ]

    data = longterm.build_longterm(records, 2018, 2020)

    assert data["years"] == [2018, 2020]
    assert data["records_by_year"] == {"2018": 2, "2020": 1}
    marker = data["markers"][0]
    assert marker["name"]
    assert marker["years"]["2018"]["median"] == 130
    assert marker["years"]["2018"]["count"] == 2
    assert marker["measured_years"] == 2


def test_longterm_persistent_high_flag():
    records = [
        _rec(y - 2017, f"{y}-01-01", [{"name": "Глюкоза", "value": 8.0, "unit": "ммоль/л", "reference_range": "3.9-6.1"}])
        for y in (2018, 2019, 2020, 2021)
    ]

    data = longterm.build_longterm(records, 2018, 2025)

    marker = data["markers"][0]
    assert marker["flag"] == "persistent_high"
    assert marker["years"]["2018"]["status"] == "high"


def test_longterm_improving_flag():
    records = [
        _rec(1, "2018-01-01", [{"name": "Глюкоза", "value": 8.0, "unit": "ммоль/л", "reference_range": "3.9-6.1"}]),
        _rec(2, "2019-01-01", [{"name": "Глюкоза", "value": 7.5, "unit": "ммоль/л", "reference_range": "3.9-6.1"}]),
        _rec(3, "2021-01-01", [{"name": "Глюкоза", "value": 5.2, "unit": "ммоль/л", "reference_range": "3.9-6.1"}]),
    ]

    data = longterm.build_longterm(records, 2018, 2025)

    assert data["markers"][0]["flag"] == "improving"


def test_longterm_skips_suspect_and_filters_period():
    records = [
        _rec(1, "2015-01-01", [{"name": "HGB", "value": 100, "unit": "г/л", "reference_range": "120-160"}]),
        _rec(2, "2020-01-01", [{"name": "HGB", "value": 140, "unit": "г/л", "reference_range": "120-160"}]),
    ]

    data = longterm.build_longterm(records, 2018, 2025)

    assert data["years"] == [2020]
    assert data["markers"][0]["total"] == 1


def test_prompt_text_contains_marker_and_years():
    records = [
        _rec(1, "2018-01-01", [{"name": "HGB", "value": 140, "unit": "г/л", "reference_range": "120-160"}]),
        _rec(2, "2020-01-01", [{"name": "HGB", "value": 150, "unit": "г/л", "reference_range": "120-160"}]),
    ]

    data = longterm.build_longterm(records, 2018, 2020)
    text = longterm.to_prompt_text(data)

    assert data["markers"][0]["name"] in text
    assert "2018" in text and "2020" in text


def test_longterm_endpoint_with_stored_records(db):
    from app.routes import records as records_route

    db.create_record(
        source_name="lab",
        summary="",
        markers=[
            {"name": "HGB", "value": 140, "unit": "г/л", "reference_range": "120-160"}
        ],
        date="2018-01-01",
    )
    db.create_record(
        source_name="lab",
        summary="",
        markers=[
            {"name": "Гемоглобин", "value": 150, "unit": "г/л", "reference_range": "120-160"}
        ],
        date="2020-01-01",
    )

    data = records_route.get_longterm(from_year=2018, to_year=2020)

    assert data["years"] == [2018, 2020]
    assert data["records_total"] == 2
    assert data["markers"][0]["measured_years"] == 2
