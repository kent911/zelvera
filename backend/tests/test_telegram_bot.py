# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
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
