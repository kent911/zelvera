# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import analysis, articles, backup, chat, documents, kiwix, logs, memory, notes, profiles, records, reminders
from app.routes import settings as settings_route
from app.services import audit, database, settings_store
from app.services.logger import logger
from app.services.telegram_bot import bot as telegram_bot

if getattr(sys, "frozen", False):
    FRONTEND_DIR = Path(sys._MEIPASS) / "frontend"
else:
    FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Zelvera", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(settings_route.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(reminders.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(kiwix.router, prefix="/api")
app.include_router(memory.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Непойманное исключение: %s %s -> %r",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})


@app.on_event("startup")
async def on_startup() -> None:
    database.init_db()
    backend = settings_store.llm_backend()
    model = settings_store.get("chat_model")
    audit.log_action("app_start", f"backend={backend}, model={model}")
    logger.info(
        "Приложение запущено (pid=%d, backend=%s, model=%s)",
        os.getpid(),
        backend,
        model,
    )
    await telegram_bot.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await telegram_bot.stop()
    audit.log_action("app_stop", "остановка приложения")

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
