# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import audit, database, i18n, memory
from app.services.logger import logger

router = APIRouter()


class MemoryFactIn(BaseModel):
    category: str = "other"
    key: str
    value: str
    evidence: str = ""


@router.get("/memory")
def get_memory() -> dict[str, Any]:
    return memory.snapshot()


@router.post("/memory/facts")
def create_fact(body: MemoryFactIn) -> dict[str, Any]:
    key = " ".join((body.key or "").split())[:80]
    value = " ".join((body.value or "").split())[:240]
    if not key or not value:
        raise HTTPException(status_code=400, detail=i18n.t("tool.save_memory_fact.empty"))
    category = (body.category or "other").strip().lower() or "other"
    if category not in memory.FACT_CATEGORIES:
        category = "other"
    fact = database.upsert_memory_fact(
        category,
        key,
        value,
        profile_id=memory.current_profile_id(),
        evidence=body.evidence,
        source="ui",
    )
    audit.log_action("memory_fact_save", f"{fact['category']}:{fact['key']}")
    return fact


@router.delete("/memory/facts/{fact_id}")
def delete_fact(fact_id: int) -> dict[str, bool]:
    if not memory.forget_fact(fact_id):
        raise HTTPException(status_code=404, detail=i18n.t("memory.not_found"))
    audit.log_action("memory_fact_delete", f"id={fact_id}")
    return {"ok": True}


@router.delete("/memory")
def reset_memory() -> dict[str, bool]:
    memory.reset()
    audit.log_action("memory_reset", "cleared L0-L3")
    logger.info(i18n.t("audit.memory_reset"))
    return {"ok": True}
