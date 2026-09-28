# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import asyncio

from app.services import i18n, memory, tools


def test_memory_layers_store_and_recall(db, monkeypatch):
    profile = db.create_profile("Egor", 1985)
    pid = profile["id"]
    monkeypatch.setattr(memory, "_profile_id", lambda: pid)
    monkeypatch.setattr(tools, "_current_profile_id", lambda: pid)

    memory.remember_turn("у меня аллергия на пенициллин", "Буду это учитывать.", pid)
    db.upsert_memory_fact(
        "allergy", "пенициллин", "аллергия", profile_id=pid, source="chat"
    )
    db.add_memory_summary("Пользователь сообщил об аллергии на пенициллин.", pid)
    db.set_memory_portrait(pid, "Аллергия на пенициллин.")

    snap = memory.snapshot(pid)
    assert snap["messages"] == 2
    assert snap["facts"][0]["key"] == "пенициллин"
    assert "Аллергия" in snap["portrait"]["content"]

    ctx = memory.recall_context("аллергия", pid)
    assert "пенициллин" in ctx
    assert "Аллергия на пенициллин" in ctx

    found = tools.search_memory("пенициллин")
    assert "пенициллин" in found
    listed = tools.list_memory()
    assert "аллергия" in listed.lower() or "пенициллин" in listed


def test_save_memory_fact_tool(db, monkeypatch):
    profile = db.create_profile("Egor")
    monkeypatch.setattr(tools, "_current_profile_id", lambda: profile["id"])
    text = tools.save_memory_fact("allergy", "йод", "непереносимость")
    assert "йод" in text
    facts = db.list_memory_facts(profile["id"])
    assert facts[0]["value"] == "непереносимость"


def test_memory_upsert_updates_same_key(db):
    profile = db.create_profile("Egor")
    db.upsert_memory_fact("lifestyle", "сон", "мало сплю", profile_id=profile["id"])
    db.upsert_memory_fact("lifestyle", "сон", "сплю 5 часов", profile_id=profile["id"])
    facts = db.list_memory_facts(profile["id"])
    assert len(facts) == 1
    assert facts[0]["value"] == "сплю 5 часов"


def test_memory_reset(db, monkeypatch):
    profile = db.create_profile("Egor")
    pid = profile["id"]
    monkeypatch.setattr(memory, "_profile_id", lambda: pid)
    db.upsert_memory_fact("other", "кофе", "пьёт много", profile_id=pid)
    memory.reset(pid)
    assert db.list_memory_facts(pid) == []
    assert tools.list_memory() == i18n.t("tool.list_memory.empty")


def test_should_skip_lab_queries():
    assert memory._should_extract("у меня аллергия на пыльцу и плохо сплю")
    assert not memory._should_extract("покажи мои последние анализы")
    assert not memory._should_extract("Что ты обо мне помнишь?")
    assert not memory._should_extract("ок")


def test_extract_skips_lab_numbers(db, monkeypatch):
    profile = db.create_profile("Egor")
    pid = profile["id"]

    async def fake_complete(_messages):
        return (
            '{"facts": ['
            '{"category": "other", "key": "холестерин", "value": "6.2 ммоль"},'
            '{"category": "allergy", "key": "пенициллин", "value": "аллергия"}'
            "]}"
        )

    monkeypatch.setattr(memory.llm, "complete", fake_complete)
    asyncio.run(memory._extract_facts("холестерин 6.2 и аллергия", "учту", pid))
    facts = db.list_memory_facts(pid)
    assert len(facts) == 1
    assert facts[0]["key"] == "пенициллин"


def test_trim_keeps_last_messages(db, monkeypatch):
    profile = db.create_profile("Egor")
    pid = profile["id"]
    monkeypatch.setattr(memory, "L0_KEEP", 4)
    for i in range(5):
        memory.remember_turn(f"сообщение пользователя номер {i}", f"ответ {i}", pid)
    assert db.count_memory_messages(pid) == 4
    rows = db.list_memory_messages(pid, 40)
    assert rows[0]["content"].endswith("3") or "3" in rows[0]["content"]


def test_extract_json_from_fenced_block():
    raw = '```json\n{"facts": [{"category": "allergy", "key": "пыльца", "value": "сезонно"}]}\n```'
    data = memory._extract_json(raw)
    assert data["facts"][0]["key"] == "пыльца"


def test_extract_facts_skips_empty_and_saves(db, monkeypatch):
    profile = db.create_profile("Egor")
    pid = profile["id"]

    async def fake_complete(_messages):
        return '{"facts": [{"category": "allergy", "key": "пенициллин", "value": "аллергия", "evidence": "сказал"}]}'

    monkeypatch.setattr(memory.llm, "complete", fake_complete)
    asyncio.run(memory._extract_facts("у меня аллергия на пенициллин", "учту", pid, "telegram"))
    facts = db.list_memory_facts(pid)
    assert len(facts) == 1
    assert facts[0]["key"] == "пенициллин"
    assert facts[0]["source"] == "telegram"


def test_recall_empty_when_no_facts(db):
    profile = db.create_profile("Egor")
    assert memory.recall_context("сон", profile["id"]) == ""


def test_memory_isolated_by_profile(db, monkeypatch):
    a = db.create_profile("A")
    b = db.create_profile("B")
    db.upsert_memory_fact("allergy", "пенициллин", "аллергия", profile_id=a["id"])
    db.upsert_memory_fact("lifestyle", "сон", "мало сплю", profile_id=b["id"])

    ctx = memory.recall_context("аллергия", a["id"])
    assert "пенициллин" in ctx
    assert "сон" not in ctx

    monkeypatch.setattr(tools, "_current_profile_id", lambda: a["id"])
    listed = tools.list_memory()
    assert "пенициллин" in listed
    assert "сон" not in listed


def test_forget_fact_stays_in_profile(db, monkeypatch):
    a = db.create_profile("A")
    b = db.create_profile("B")
    fa = db.upsert_memory_fact("allergy", "йод", "нельзя", profile_id=a["id"])
    fb = db.upsert_memory_fact("allergy", "йод", "нельзя", profile_id=b["id"])
    monkeypatch.setattr(memory, "_profile_id", lambda: a["id"])
    assert memory.forget_fact(fb["id"]) is False
    assert db.list_memory_facts(b["id"])
    assert memory.forget_fact(fa["id"]) is True
    assert db.list_memory_facts(a["id"]) == []


def test_none_profile_does_not_leak_or_wipe(db):
    a = db.create_profile("A")
    db.upsert_memory_fact("allergy", "йод", "нельзя", profile_id=a["id"])
    db.add_memory_summary("итог", a["id"])
    memory.remember_turn("у меня аллергия на йод", "учту", a["id"])
    assert db.list_memory_facts(None) == []
    assert db.list_memory_summaries(None) == []
    assert db.list_memory_messages(None) == []
    assert db.count_memory_messages(None) == 0
    assert memory.recall_context("йод", None) == ""
    memory.reset(None)
    assert db.list_memory_facts(a["id"])


def test_get_tools_follows_language(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")
    names = [t["function"]["name"] for t in tools.get_tools()]
    assert "search_memory" in names
    assert "save_memory_fact" in names
    desc = next(t["function"]["description"] for t in tools.get_tools() if t["function"]["name"] == "list_memory")
    assert "long-term" in desc.lower() or "memory" in desc.lower()


def test_profile_id_falls_back_to_first(db, monkeypatch):
    monkeypatch.setattr(memory.settings_store, "get_current_profile_id", lambda: None)
    profiles = db.list_profiles()
    assert profiles
    assert memory.current_profile_id() == profiles[0]["id"]
