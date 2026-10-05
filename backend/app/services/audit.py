# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Аудит действий пользователя.

Записывает, что и когда делал пользователь: запросы в чате, загрузка
документов, сохранение заметок, вызов инструментов ИИ, настройки.
Хранится в SQLite (таблица audit_log).
"""
from typing import Any

from app.services import database

ACTION_LABELS: dict[str, str] = {
    "app_start": "Запуск приложения",
    "chat": "Запрос в чате",
    "analysis": "Аналитический отчёт",
    "document_extract": "Распознавание документа",
    "record_create": "Добавление записи в карту",
    "record_delete": "Удаление записи из карты",
    "export_pdf": "Экспорт карты в PDF",
    "article_upload": "Загрузка статьи",
    "article_delete": "Удаление статьи",
    "article_search": "Поиск по статьям",
    "note_create": "Сохранение заметки",
    "note_delete": "Удаление заметки",
    "note_export": "Экспорт заметок в PDF",
    "profile_create": "Создание профиля",
    "profile_rename": "Переименование профиля",
    "profile_activate": "Переключение профиля",
    "profile_delete": "Удаление профиля",
    "reminder_create": "Создание напоминания",
    "reminder_delete": "Удаление напоминания",
    "auth_setup": "Создание входа",
    "auth_login": "Вход",
    "auth_password": "Смена пароля",
    "auth_reset_request": "Запрос сброса пароля",
    "auth_reset": "Сброс пароля",
    "settings_update": "Изменение настроек",
    "model_pull": "Скачивание модели",
    "logs_clear": "Очистка журнала",
    "tool_call": "Вызов инструмента ИИ",
    "memory_fact_save": "Сохранение факта памяти",
    "memory_fact_delete": "Удаление факта памяти",
    "memory_reset": "Очистка памяти ассистента",
    "error": "Ошибка",
}


def label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def log_action(action: str, detail: str = "") -> None:
    try:
        database.add_audit(action, detail)
    except Exception:
        # аудит не должен ломать основную логику
        pass


def _truncate(text: str, limit: int = 160) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def log_chat(text: str) -> None:
    log_action("chat", _truncate(text))


def log_document(filename: str, marker_count: int) -> None:
    log_action(
        "document_extract",
        f"{filename} — распознано показателей: {marker_count}",
    )


def log_tool_call(name: str, arguments: dict[str, Any]) -> None:
    args = arguments or {}
    if name == "search_articles":
        detail = f"search_articles(query=\"{_truncate(str(args.get('query', '')))}\")"
    else:
        detail = f"{name}({', '.join(f'{k}={v}' for k, v in list(args.items())[:3])})"
    log_action("tool_call", _truncate(detail))
