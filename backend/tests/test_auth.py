# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from app.services import auth


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DATA_DIR", tmp_path)
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    auth.reset_cache()


def test_setup_login_and_session(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert not auth.is_configured()
    auth.setup("egor", "secret123")
    assert auth.is_configured()
    assert auth.username() == "egor"
    assert auth.verify_login("egor", "secret123")
    assert not auth.verify_login("egor", "wrongpass")
    assert not auth.verify_login("other", "secret123")
    token = auth.make_session_token()
    assert auth.session_username(token) == "egor"
    assert auth.session_username("bad") is None


def test_setup_rejects_short_and_duplicate(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    try:
        auth.setup("e", "secret123")
        assert False
    except ValueError as exc:
        assert str(exc) == "username"
    try:
        auth.setup("egor", "short")
        assert False
    except ValueError as exc:
        assert str(exc) == "password"
    auth.setup("egor", "secret123")
    try:
        auth.setup("other", "secret123")
        assert False
    except ValueError as exc:
        assert str(exc) == "exists"


def test_change_password(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    auth.setup("egor", "secret123")
    old_token = auth.make_session_token()
    auth.change_password("secret123", "newpass12")
    assert not auth.verify_login("egor", "secret123")
    assert auth.verify_login("egor", "newpass12")
    assert auth.session_username(old_token) is None
    assert auth.session_username(auth.make_session_token()) == "egor"


def test_api_requires_login(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.config import DATA_DIR as _unused  # noqa: F401
    from app.services import database
    from app.services.telegram_bot import bot as telegram_bot

    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(telegram_bot, "start", _noop)
    monkeypatch.setattr(telegram_bot, "stop", _noop)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        status = client.get("/api/auth/status").json()
        assert status["configured"] is False
        assert client.get("/api/config").status_code == 401
        created = client.post(
            "/api/auth/setup",
            json={"username": "egor", "password": "secret123"},
        )
        assert created.status_code == 200
        assert client.get("/api/config").status_code == 200
        client.post("/api/auth/logout")
        assert client.get("/api/config").status_code == 401
        bad = client.post(
            "/api/auth/login",
            json={"username": "egor", "password": "nope1234"},
        )
        assert bad.status_code == 401
        ok = client.post(
            "/api/auth/login",
            json={"username": "egor", "password": "secret123"},
        )
        assert ok.status_code == 200
        assert client.get("/api/config").status_code == 200
        assert status.get("recovery") is False


def test_reset_password_with_code(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.services import mailer, settings_store

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(recovery_email="you@example.com", smtp_host="smtp.example.com")
    auth.setup("egor", "secret123")
    sent: list[str] = []

    def _fake_send(code: str) -> None:
        sent.append(code)

    monkeypatch.setattr(mailer, "send_reset_code", _fake_send)
    assert auth.recovery_available()
    auth.request_reset()
    assert len(sent) == 1
    try:
        auth.confirm_reset("000000", "newpass12")
        assert False
    except ValueError as exc:
        assert str(exc) == "code"
    auth.confirm_reset(sent[0], "newpass12")
    assert not auth.verify_login("egor", "secret123")
    assert auth.verify_login("egor", "newpass12")


def test_reset_requires_smtp(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.services import settings_store

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    auth.setup("egor", "secret123")
    assert not auth.recovery_available()
    try:
        auth.request_reset()
        assert False
    except ValueError as exc:
        assert str(exc) == "smtp"


def test_reset_rate_limit(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.services import mailer, settings_store

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(recovery_email="you@example.com", smtp_host="smtp.example.com")
    auth.setup("egor", "secret123")
    monkeypatch.setattr(mailer, "send_reset_code", lambda _code: None)
    auth.request_reset()
    try:
        auth.request_reset()
        assert False
    except ValueError as exc:
        assert str(exc) == "rate"


def test_login_lockout_after_failures(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    auth.setup("egor", "secret123")
    for _ in range(auth.LOGIN_MAX_FAILS - 1):
        assert auth.attempt_login("egor", "wrongpass") is False
    try:
        auth.attempt_login("egor", "wrongpass")
        assert False
    except ValueError as exc:
        assert str(exc) == "locked"
    try:
        auth.attempt_login("egor", "secret123")
        assert False
    except ValueError as exc:
        assert str(exc) == "locked"
    assert auth.lock_remaining_min() >= 1
    data = dict(auth._load())
    data["login_lock"] = "1"
    auth._save(data)
    assert auth.attempt_login("egor", "secret123") is True


def test_reset_password_invalidates_old_session(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from app.services import mailer, settings_store

    monkeypatch.setattr(settings_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_store, "_cache", None)
    settings_store.update(recovery_email="you@example.com", smtp_host="smtp.example.com")
    auth.setup("egor", "secret123")
    old_token = auth.make_session_token()
    sent: list[str] = []
    monkeypatch.setattr(mailer, "send_reset_code", sent.append)
    auth.request_reset()
    auth.confirm_reset(sent[0], "newpass12")
    assert auth.session_username(old_token) is None
