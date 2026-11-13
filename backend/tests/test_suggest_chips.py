# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import json

from app.services import settings_store


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)


def test_suggest_chips_empty_by_default(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert settings_store.suggest_chips() == []
    assert settings_store.get("suggest_chips") == ""


def test_suggest_chips_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.update(
        suggest_chips=json.dumps(["Покажи анализы", "Что помнишь?"], ensure_ascii=False)
    )
    assert settings_store.suggest_chips() == ["Покажи анализы", "Что помнишь?"]


def test_suggest_chips_drops_empty_and_trims(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.update(suggest_chips=json.dumps(["  вопрос  ", "", "   ", 42, None]))
    assert settings_store.suggest_chips() == ["вопрос"]


def test_suggest_chips_limits_count_and_length(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    items = [f"q{i}-" + "x" * 500 for i in range(20)]
    settings_store.update(suggest_chips=json.dumps(items))
    saved = settings_store.suggest_chips()
    assert len(saved) == settings_store.SUGGEST_CHIPS_MAX
    assert all(len(item) <= settings_store.SUGGEST_CHIP_MAX_LEN for item in saved)


def test_suggest_chips_invalid_json_resets(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.update(suggest_chips=json.dumps(["ok"]))
    settings_store.update(suggest_chips="{not json")
    assert settings_store.suggest_chips() == []


def test_suggest_chips_non_list_resets(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.update(suggest_chips=json.dumps(["ok"]))
    settings_store.update(suggest_chips=json.dumps({"a": 1}))
    assert settings_store.suggest_chips() == []


def test_suggest_chips_blank_resets_to_defaults(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    settings_store.update(suggest_chips=json.dumps(["ok"]))
    settings_store.update(suggest_chips="")
    assert settings_store.suggest_chips() == []


def test_suggest_chips_api_roundtrip(tmp_path, monkeypatch):
    from app.services import auth, database
    from app.services.telegram_bot import bot as telegram_bot

    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    auth.reset_cache()
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(telegram_bot, "start", _noop)
    monkeypatch.setattr(telegram_bot, "stop", _noop)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        assert client.post(
            "/api/auth/setup", json={"username": "egor", "password": "secret123"}
        ).status_code == 200
        payload = json.dumps(["Первый", "  Второй  ", ""], ensure_ascii=False)
        saved = client.post("/api/settings", json={"suggest_chips": payload})
        assert saved.status_code == 200
        got = client.get("/api/settings").json()
        assert got["suggest_chips"] == json.dumps(["Первый", "Второй"], ensure_ascii=False)
        client.post("/api/settings", json={"suggest_chips": ""})
        assert client.get("/api/settings").json()["suggest_chips"] == ""
