# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Локальная иерархическая память агента (L0-L3).

L0 — сырые реплики диалога (SQLite memory_messages).
L1 — стабильные факты о пользователе (аллергии, жалобы, привычки).
L2 — сжатые саммари недавних диалогов.
L3 — короткий портрет профиля.

Данные остаются в data/medical.db, без облака.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.services import database, i18n, llm, settings_store

log = logging.getLogger("memory")

L0_KEEP = 80
L1_RECALL_LIMIT = 8
L2_RECALL_LIMIT = 3
CONTEXT_BUDGET = 1800
EXTRACT_AFTER_TURNS = 2
SUMMARIZE_EVERY = 8
PORTRAIT_EVERY = 4
FACT_CATEGORIES = (
    "allergy",
    "condition",
    "medication",
    "lifestyle",
    "preference",
    "family",
    "symptom",
    "other",
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_SKIP_USER = re.compile(
    r"^(покажи|покажи мне|что там|какие у меня|как изменил|"
    r"сформируй|сохрани|добавь|найди|есть ли|"
    r"что ты (обо мне )?помнишь|what do you remember|"
    r"show|what are my|how did|save |add |find )",
    re.IGNORECASE,
)
_LAB_VALUE = re.compile(
    r"(?:^|[\s:=])[-+]?\d+(?:[.,]\d+)?\s*(?:мг|г/л|ммоль|мме|ед|%|mmHg|mg/dl|mmol)",
    re.IGNORECASE,
)


def current_profile_id() -> int | None:
    pid = settings_store.get_current_profile_id()
    if pid is not None:
        return pid
    try:
        profiles = database.list_profiles()
    except Exception:
        return None
    return profiles[0]["id"] if profiles else None


def _profile_id() -> int | None:
    return current_profile_id()


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _should_extract(user_text: str) -> bool:
    text = " ".join((user_text or "").split())
    if len(text) < 12:
        return False
    if _SKIP_USER.match(text):
        return False
    return True


def remember_turn(
    user_text: str,
    assistant_text: str,
    profile_id: int | None = None,
    channel: str = "web",
    session_id: str = "",
) -> None:
    pid = profile_id if profile_id is not None else _profile_id()
    if (user_text or "").strip():
        database.add_memory_message(
            "user", user_text, profile_id=pid, channel=channel, session_id=session_id
        )
    if (assistant_text or "").strip():
        database.add_memory_message(
            "assistant",
            assistant_text,
            profile_id=pid,
            channel=channel,
            session_id=session_id,
        )
    database.trim_memory_messages(pid, L0_KEEP)


def recall_context(query: str, profile_id: int | None = None) -> str:
    pid = profile_id if profile_id is not None else _profile_id()
    parts: list[str] = []

    portrait = database.get_memory_portrait(pid) if pid is not None else None
    if portrait and (portrait.get("content") or "").strip():
        parts.append(i18n.t("memory.l3_block", text=portrait["content"].strip()))

    facts = database.search_memory_facts(query, pid, L1_RECALL_LIMIT)
    if not facts:
        facts = database.list_memory_facts(pid)[:L1_RECALL_LIMIT]
    if facts:
        lines = [
            i18n.t(
                "memory.fact_line",
                category=f.get("category") or "other",
                name=f.get("key") or "",
                value=f.get("value") or "",
            )
            for f in facts
        ]
        parts.append(i18n.t("memory.l1_block", items="\n".join(lines)))

    summaries = database.list_memory_summaries(pid, L2_RECALL_LIMIT)
    if summaries:
        texts = [s.get("content") or "" for s in summaries if s.get("content")]
        if texts:
            parts.append(i18n.t("memory.l2_block", text="\n\n".join(texts)))

    if not parts:
        return ""
    blob = "\n\n".join(parts)
    if len(blob) > CONTEXT_BUDGET:
        blob = blob[: CONTEXT_BUDGET - 1].rstrip() + "…"
    return i18n.t("memory.context_header") + "\n" + blob


def snapshot(profile_id: int | None = None) -> dict[str, Any]:
    pid = profile_id if profile_id is not None else _profile_id()
    portrait = database.get_memory_portrait(pid) if pid is not None else None
    return {
        "profile_id": pid,
        "messages": database.count_memory_messages(pid),
        "facts": database.list_memory_facts(pid),
        "summaries": database.list_memory_summaries(pid, 12),
        "portrait": portrait,
    }


def forget_fact(fact_id: int, profile_id: int | None = None) -> bool:
    pid = profile_id if profile_id is not None else _profile_id()
    return database.delete_memory_fact(fact_id, pid)


def reset(profile_id: int | None = None) -> None:
    pid = profile_id if profile_id is not None else _profile_id()
    database.clear_memory(pid)


async def ingest_turn(
    user_text: str,
    assistant_text: str,
    profile_id: int | None = None,
    channel: str = "web",
    session_id: str = "",
) -> None:
    pid = profile_id if profile_id is not None else _profile_id()
    remember_turn(user_text, assistant_text, pid, channel, session_id)
    try:
        # count() упирается в L0_KEEP, поэтому для расписания берём монотонный id:
        # иначе после заполнения L0 саммари писалось бы на каждом ходу.
        seq = database.max_memory_message_id(pid)
        tasks = []
        if _should_extract(user_text):
            tasks.append(_extract_facts(user_text, assistant_text, pid, channel))
        if seq >= SUMMARIZE_EVERY and seq % SUMMARIZE_EVERY < 2:
            tasks.append(_summarize_recent(pid, session_id))
        fact_count = len(database.list_memory_facts(pid))
        if fact_count and (
            seq % PORTRAIT_EVERY < 2 or not database.get_memory_portrait(pid)
        ):
            tasks.append(_refresh_portrait(pid))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        log.debug("memory ingest skipped", exc_info=True)


_background_tasks: set[asyncio.Task] = set()


def schedule_ingest(
    user_text: str,
    assistant_text: str,
    profile_id: int | None = None,
    channel: str = "web",
    session_id: str = "",
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    # Ссылку на задачу надо держать: loop хранит только weakref,
    # иначе ingest может быть собран GC посреди работы.
    task = loop.create_task(
        ingest_turn(user_text, assistant_text, profile_id, channel, session_id)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _extract_facts(
    user_text: str,
    assistant_text: str,
    profile_id: int | None,
    channel: str = "web",
) -> None:
    prompt = i18n.t(
        "memory.extract_prompt",
        user=user_text[:1200],
        assistant=(assistant_text or "")[:800],
    )
    try:
        raw = await llm.complete(
            [
                {"role": "system", "content": i18n.t("memory.extract_system")},
                {"role": "user", "content": prompt},
            ]
        )
    except Exception:
        log.debug("memory extract llm failed", exc_info=True)
        return
    data = _extract_json(raw) or {}
    facts = data.get("facts")
    if not isinstance(facts, list):
        return
    saved = 0
    for item in facts[:6]:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "other").strip().lower()
        if category not in FACT_CATEGORIES:
            category = "other"
        key = str(item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        if not key or not value:
            continue
        if _LAB_VALUE.search(key) or _LAB_VALUE.search(value):
            continue
        try:
            database.upsert_memory_fact(
                category,
                key[:80],
                value[:240],
                profile_id=profile_id,
                evidence=str(item.get("evidence") or "")[:240],
                source="telegram" if channel == "telegram" else "chat",
            )
            saved += 1
        except ValueError:
            continue
    if saved:
        log.info("memory L1: saved %d facts", saved)


async def _summarize_recent(profile_id: int | None, session_id: str) -> None:
    rows = database.list_memory_messages(profile_id, L0_KEEP)
    if len(rows) < EXTRACT_AFTER_TURNS * 2:
        return
    recent = rows[-16:]
    dialog = "\n".join(
        f"{r.get('role')}: {r.get('content')}" for r in recent if r.get("content")
    )
    try:
        raw = await llm.complete(
            [
                {"role": "system", "content": i18n.t("memory.summary_system")},
                {
                    "role": "user",
                    "content": i18n.t("memory.summary_prompt", dialog=dialog[:4000]),
                },
            ]
        )
    except Exception:
        log.debug("memory summary llm failed", exc_info=True)
        return
    text = " ".join((raw or "").split())
    if len(text) < 20:
        return
    database.add_memory_summary(
        text[:800],
        profile_id=profile_id,
        session_id=session_id,
        turn_count=len(recent),
    )


async def _refresh_portrait(profile_id: int | None) -> None:
    if profile_id is None:
        return
    facts = database.list_memory_facts(profile_id)
    if not facts:
        return
    lines = [
        f"- [{f.get('category')}] {f.get('key')}: {f.get('value')}" for f in facts[:20]
    ]
    summaries = database.list_memory_summaries(profile_id, 3)
    extra = "\n".join(s.get("content") or "" for s in summaries)
    try:
        raw = await llm.complete(
            [
                {"role": "system", "content": i18n.t("memory.portrait_system")},
                {
                    "role": "user",
                    "content": i18n.t(
                        "memory.portrait_prompt",
                        facts="\n".join(lines),
                        summaries=extra[:1200],
                    ),
                },
            ]
        )
    except Exception:
        log.debug("memory portrait llm failed", exc_info=True)
        return
    text = " ".join((raw or "").split())
    if len(text) < 12:
        return
    database.set_memory_portrait(profile_id, text[:600])
