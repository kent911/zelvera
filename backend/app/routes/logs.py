# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from typing import Any

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import DATA_DIR
from app.services import audit, database, i18n, logger

router = APIRouter()

LOG_FILE = DATA_DIR / "app.log"

FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(message)s")


class ClientLogIn(BaseModel):
    level: str = "error"
    message: str
    stack: str = ""
    url: str = ""
    user_agent: str = ""


@router.get("/logs")
async def get_logs() -> dict:
    if not LOG_FILE.exists():
        return {"logs": []}
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"logs": lines[-200:]}


@router.delete("/logs")
async def clear_logs() -> dict[str, bool]:
    logger.clear_log()
    audit.log_action("logs_clear", "Журнал очищен")
    return {"ok": True}


@router.get("/logs/download")
async def download_logs() -> FileResponse:
    if not LOG_FILE.exists():
        raise HTTPException(status_code=404, detail=i18n.t("logs.not_created"))
    return FileResponse(
        LOG_FILE,
        media_type="text/plain",
        filename="zelvera-app.log",
    )


@router.post("/logs/client")
async def client_log(body: ClientLogIn) -> dict:
    root = logging.getLogger("zelvera")
    level = (body.level or "error").lower()
    if level not in {"debug", "info", "warning", "error", "critical"}:
        level = "error"
    message = f"[фронтенд] {body.message} (url: {body.url})"
    if body.stack:
        message += f"\n{body.stack}"
    root.log(getattr(logging, level.upper()), message)
    if level in {"warning", "error", "critical"}:
        audit.log_action("error", f"{body.message} (url: {body.url})")
    return {"ok": True}


@router.get("/audit")
async def get_audit(
    action: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=5000),
) -> dict[str, Any]:
    return {
        "items": database.list_audit(action, limit),
        "actions": database.audit_actions(),
        "labels": {k: i18n.t(f"audit.{k}") for k in audit.ACTION_LABELS},
    }


@router.delete("/audit")
async def clear_audit() -> dict[str, bool]:
    database.clear_audit()
    return {"ok": True}
