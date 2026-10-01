# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import settings_store


def test_normalize_openai_base_url_adds_v1():
    assert settings_store.normalize_openai_base_url("http://192.168.1.100:8080") == (
        "http://192.168.1.100:8080/v1"
    )
    assert settings_store.normalize_openai_base_url("http://192.168.1.100:8080/v1") == (
        "http://192.168.1.100:8080/v1"
    )
    assert settings_store.normalize_openai_base_url("http://192.168.1.100:8080/") == (
        "http://192.168.1.100:8080/v1"
    )
    assert settings_store.normalize_openai_base_url("") == ""


def test_update_openai_backend_and_url(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    saved = settings_store.update(
        llm_backend="openai",
        openai_base_url="http://192.168.1.100:8080",
        openai_api_key="",
        chat_model="bonsai2-27B",
    )
    assert saved["llm_backend"] == "openai"
    assert saved["openai_base_url"] == "http://192.168.1.100:8080/v1"
    assert saved["openai_api_key"] == "local"
    assert saved["chat_model"] == "bonsai2-27B"
    assert settings_store.llm_backend() == "openai"
    assert settings_store.openai_base_url() == "http://192.168.1.100:8080/v1"
    assert settings_store.openai_api_key() == "local"


def test_llm_backend_rejects_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    saved = settings_store.update(llm_backend="something-else")
    assert saved["llm_backend"] == "ollama"
    assert settings_store.llm_backend() == "ollama"
