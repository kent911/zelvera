# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio
from datetime import datetime, timedelta

from app.services import telegram_bot


def test_parse_allowed_ids_handles_separators():
    assert telegram_bot._parse_allowed_ids("1, 2;3\n4 5") == {1, 2, 3, 4, 5}
    assert telegram_bot._parse_allowed_ids("") == set()
    assert telegram_bot._parse_allowed_ids("abc, 7, -9") == {7, -9}


def test_split_message_short_and_empty():
    assert telegram_bot.split_message("") == []
    assert telegram_bot.split_message("  hello  ") == ["hello"]
    assert telegram_bot.split_message("x" * 100, limit=200) == ["x" * 100]


def test_split_message_keeps_paragraphs_and_limits():
    text = "\n\n".join(["para " + str(i) + " " + "y" * 60 for i in range(20)])
    parts = telegram_bot.split_message(text, limit=300)
    assert len(parts) > 1
    assert all(len(part) <= 300 for part in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_split_message_splits_oversized_block():
    parts = telegram_bot.split_message("z" * 500, limit=100)
    assert [len(p) for p in parts] == [100, 100, 100, 100, 100]
    assert "".join(parts) == "z" * 500


def test_days_since():
    today = datetime.now().strftime("%Y-%m-%d")
    assert telegram_bot._days_since(today) == 0
    old = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 09:00")
    assert telegram_bot._days_since(old) == 30
    assert telegram_bot._days_since("") is None
    assert telegram_bot._days_since("not-a-date") is None


def test_database_create_from_telegram_sets_profile(db, monkeypatch):
    profile = db.create_profile("Tg user", 1980)
    monkeypatch.setattr(
        telegram_bot.tools, "_current_profile_id", lambda: profile["id"]
    )
    parsed = {
        "summary": "",
        "date": "2026-01-02",
        "markers": [{"name": "HGB", "value": 140, "unit": "г/л"}],
    }
    record = telegram_bot.database_create_from_telegram(parsed)
    assert record["profile_id"] == profile["id"]
    assert record["markers"]
    assert db.list_records(profile["id"])


def test_client_options_prefers_proxy_then_ipv4(monkeypatch):
    bot = telegram_bot.TelegramBot()
    store: dict[str, str] = {}

    monkeypatch.setattr(telegram_bot.settings_store, "get", lambda key: store.get(key, "1"))

    store["telegram_proxy"] = "socks5://localhost:1080"
    assert bot.client_options() == {"proxy": "socks5://localhost:1080"}

    store["telegram_proxy"] = ""
    store["telegram_force_ipv4"] = "1"
    options = bot.client_options()
    assert "transport" in options
    assert isinstance(options["transport"], telegram_bot.httpx.AsyncHTTPTransport)

    store["telegram_force_ipv4"] = "0"
    assert bot.client_options() == {}


def test_lock_prevents_second_instance(monkeypatch, tmp_path):
    monkeypatch.setattr(telegram_bot, "LOCK_PATH", tmp_path / "telegram.lock")
    first = telegram_bot.TelegramBot()
    second = telegram_bot.TelegramBot()

    assert first._acquire_lock() is True
    assert second._acquire_lock() is False

    first._release_lock()
    assert second._acquire_lock() is True
    second._release_lock()


def test_client_limits_disable_keepalive():
    limits = telegram_bot.TelegramBot().client_limits()
    assert limits.max_keepalive_connections == 0
    assert limits.max_connections == 10


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"ok": True, "result": 42}


class _FlakyClient:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def post(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise telegram_bot.httpx.ConnectError("boom")
        return _FakeResponse()


def test_api_retries_transient_network_errors(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(telegram_bot.asyncio, "sleep", no_sleep)
    bot = telegram_bot.TelegramBot()
    bot._client = _FlakyClient(failures=2)

    result = asyncio.run(bot._api("sendMessage", {"chat_id": 1, "text": "hi"}))

    assert result == 42
    assert bot._client.calls == 3


def test_api_raises_after_all_retries(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(telegram_bot.asyncio, "sleep", no_sleep)
    bot = telegram_bot.TelegramBot()
    bot._client = _FlakyClient(failures=99)

    try:
        asyncio.run(bot._api("sendMessage", {}))
    except telegram_bot.httpx.ConnectError:
        pass
    else:  # pragma: no cover
        raise AssertionError("ожидалась сетевая ошибка")

    assert bot._client.calls == telegram_bot.API_RETRIES
