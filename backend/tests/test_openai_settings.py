# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import settings_store
from app.services.llm import _openai_image_unsupported, coalesce_system_messages


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


def test_public_settings_masks_secrets_and_blank_keeps(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(
        openai_api_key="sk-secret",
        telegram_bot_token="bot-token",
        smtp_password="mail-pass",
        smtp_host="smtp.example.com",
    )
    public = settings_store.public_settings()
    assert public["openai_api_key"] == ""
    assert public["telegram_bot_token"] == ""
    assert public["smtp_password"] == ""
    assert public["openai_api_key_set"] == "1"
    assert public["telegram_bot_token_set"] == "1"
    assert public["smtp_password_set"] == "1"
    assert "sk-secret" not in public.values()
    assert "bot-token" not in public.values()
    assert "mail-pass" not in public.values()
    settings_store.update(openai_api_key="", telegram_bot_token="", smtp_password="")
    stored = settings_store.all_settings()
    assert stored["openai_api_key"] == "sk-secret"
    assert stored["telegram_bot_token"] == "bot-token"
    assert stored["smtp_password"] == "mail-pass"


def test_llm_backend_rejects_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    saved = settings_store.update(llm_backend="something-else")
    assert saved["llm_backend"] == "ollama"
    assert settings_store.llm_backend() == "ollama"


def test_coalesce_system_messages_single_leading():
    out = coalesce_system_messages(
        [
            {"role": "system", "content": "правила"},
            {"role": "system", "content": "память: аллергия на пенициллин"},
            {"role": "system", "content": "профиль: Иван"},
            {"role": "user", "content": "что нельзя принимать?"},
            {"role": "assistant", "content": "пенициллин"},
            {"role": "system", "content": "фрагменты статей"},
        ]
    )
    assert out[0]["role"] == "system"
    assert "правила" in out[0]["content"]
    assert "аллергия на пенициллин" in out[0]["content"]
    assert "профиль: Иван" in out[0]["content"]
    assert "фрагменты статей" in out[0]["content"]
    assert [m["role"] for m in out] == ["system", "user", "assistant"]
    assert all(m["role"] != "system" for m in out[1:])


def test_vision_backend_inherits_chat_then_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(llm_backend="openai")
    assert settings_store.vision_backend() == "openai"
    settings_store.update(vision_backend="ollama")
    assert settings_store.vision_backend() == "ollama"
    settings_store.update(vision_backend="")
    assert settings_store.vision_backend() == "openai"


def test_vision_backend_rejects_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(llm_backend="openai", vision_backend="nonsense")
    assert settings_store.vision_backend() == "openai"


def test_probe_llm_openai_down(tmp_path, monkeypatch):
    import asyncio

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(
        llm_backend="openai",
        openai_base_url="http://127.0.0.1:9",
        chat_model="bonsai2-27B",
    )

    async def boom(*_args, **_kwargs):
        raise ConnectionError("unreachable")

    monkeypatch.setattr(settings_store, "list_openai_models", boom)
    status = asyncio.run(settings_store.probe_llm())
    assert status["backend"] == "openai"
    assert status["model"] == "bonsai2-27B"
    assert status["reachable"] is False
    assert status["error"]


def test_probe_llm_openai_up(tmp_path, monkeypatch):
    import asyncio

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(
        llm_backend="openai",
        openai_base_url="http://127.0.0.1:8080",
        chat_model="bonsai2-27B",
    )

    async def ok(*_args, **_kwargs):
        return ["bonsai2-27B"]

    monkeypatch.setattr(settings_store, "list_openai_models", ok)
    status = asyncio.run(settings_store.probe_llm())
    assert status["reachable"] is True
    assert status["error"] == ""


def test_openai_models_empty_url_is_400(tmp_path, monkeypatch):
    from app.services import auth
    from app.services import database
    from app.services.telegram_bot import bot as telegram_bot
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    auth.reset_cache()
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(telegram_bot, "start", _noop)
    monkeypatch.setattr(telegram_bot, "stop", _noop)

    with TestClient(app) as client:
        client.post("/api/auth/setup", json={"username": "egor", "password": "secret123"})
        resp = client.post("/api/settings/openai-models", json={"openai_base_url": ""})
        assert resp.status_code == 400
        assert "адрес" in resp.json()["detail"].lower() or "specify" in resp.json()["detail"].lower()


def test_client_log_maps_warn_to_warning(tmp_path, monkeypatch, caplog):
    import logging
    from app.services import auth
    from app.services import database
    from app.services.telegram_bot import bot as telegram_bot
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    auth.reset_cache()
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(telegram_bot, "start", _noop)
    monkeypatch.setattr(telegram_bot, "stop", _noop)

    with caplog.at_level(logging.WARNING, logger="zelvera"):
        with TestClient(app) as client:
            client.post("/api/auth/setup", json={"username": "egor", "password": "secret123"})
            resp = client.post(
                "/api/logs/client",
                json={"level": "warn", "message": "HTTP 502 /api/settings/openai-models", "url": "/"},
            )
            assert resp.status_code == 200
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert not any(r.levelno >= logging.ERROR and "openai-models" in r.getMessage() for r in caplog.records)


def test_openai_image_unsupported_detects_mmproj():
    assert _openai_image_unsupported(
        Exception("image input is not supported - hint: if this is unexpected, you may need to provide the mmproj")
    )
    assert not _openai_image_unsupported(Exception("timeout connecting to llama-server"))


def test_github_proxy_saved_and_can_be_cleared(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(github_proxy="socks5h://192.168.88.100:10808")
    assert settings_store.get("github_proxy") == "socks5h://192.168.88.100:10808"
    assert settings_store.public_settings()["github_proxy"] == (
        "socks5h://192.168.88.100:10808"
    )
    settings_store.update(github_proxy="")
    assert settings_store.get("github_proxy") == ""
