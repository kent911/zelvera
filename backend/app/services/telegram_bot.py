# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Telegram-бот Zelvera: общение с ИИ, распознавание бланков, напоминания.

Работает через long-polling (getUpdates), поэтому не требует публичного
HTTPS и вебхуков. Запускается фоновой задачей внутри FastAPI, если задан
токен бота и список разрешённых Telegram ID. Токен и ID берутся из
settings_store (настройки в UI) с фолбэком на переменные окружения.
"""
from __future__ import annotations

import asyncio
import fcntl
import html
import time
from datetime import datetime
from io import BytesIO
from typing import Any

import httpx

from app.config import DATA_DIR
from app.services import (
    audit,
    document,
    extractor,
    i18n,
    kiwix,
    llm,
    settings_store,
    tools,
    validation,
    voice,
)
from app.services.logger import logger

API_BASE = "https://api.telegram.org"
POLL_TIMEOUT = 8
MESSAGE_LIMIT = 4000
HISTORY_LIMIT = 16
PHOTO_CAPTION_LIMIT = 1000
REMINDER_INTERVAL = 1800
NOTIFY_COOLDOWN = 20 * 3600
MAX_PENDING_IMAGES = 3
API_RETRIES = 3
LOCK_PATH = DATA_DIR / "telegram.lock"


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Режет длинный ответ на части по границам абзацев/строк."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
        while len(block) > limit:
            parts.append(block[:limit])
            block = block[limit:]
        current = block
    if current:
        parts.append(current)
    return parts


def _parse_allowed_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for chunk in (raw or "").replace(";", ",").replace("\n", ",").replace(" ", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            continue
    return ids


def _days_since(value: Any) -> int | None:
    if not value:
        return None
    try:
        date = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return None
    return (datetime.now() - date).days


class TelegramBot:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._reminder_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._client: httpx.AsyncClient | None = None
        self._offset = 0
        self._history: dict[int, list[dict[str, str]]] = {}
        self._pending: dict[int, dict[str, Any]] = {}
        self._notified: dict[int, float] = {}
        self._lock_file = None

    # --- конфигурация ---
    def token(self) -> str:
        return (settings_store.get("telegram_bot_token") or "").strip()

    def allowed_ids(self) -> set[int]:
        return _parse_allowed_ids(settings_store.get("telegram_allowed_ids") or "")

    def is_configured(self) -> bool:
        return bool(self.token())

    def _voice_enabled(self) -> bool:
        return (settings_store.get("telegram_voice_enabled") or "1").strip() == "1"

    def _reminders_enabled(self) -> bool:
        return (
            settings_store.get("telegram_reminders_enabled") or "1"
        ).strip() == "1"

    def proxy(self) -> str | None:
        return (settings_store.get("telegram_proxy") or "").strip() or None

    def force_ipv4(self) -> bool:
        return (settings_store.get("telegram_force_ipv4") or "1").strip() == "1"

    def client_options(self) -> dict[str, Any]:
        """Прокси или принудительный IPv4 (обход недоступного IPv6)."""
        if self.proxy():
            return {"proxy": self.proxy()}
        if self.force_ipv4():
            return {
                "transport": httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            }
        return {}

    def client_limits(self) -> httpx.Limits:
        """Без keep-alive: прокси закрывает простаивающие соединения, и httpx
        затем получает ``RemoteProtocolError`` на повторно взятом соединении."""
        return httpx.Limits(max_keepalive_connections=0, max_connections=10)

    # --- жизненный цикл ---
    def _acquire_lock(self) -> bool:
        """Не даёт двум экземплярам опрашивать одного бота одновременно."""
        try:
            LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
            lock_file = open(LOCK_PATH, "w")
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            logger.error(
                "Telegram-бот: другой процесс уже опрашивает бота (%s). "
                "Этот экземпляр не запускает polling — проверьте дубли "
                "(pgrep -af uvicorn).",
                LOCK_PATH,
            )
            return False
        self._lock_file = lock_file
        return True

    def _release_lock(self) -> None:
        if self._lock_file is None:
            return
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._lock_file.close()
        except OSError:
            pass
        self._lock_file = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        if not self.is_configured():
            logger.info(
                "Telegram-бот не запущен: не задан токен. Задайте его в «Настройки» → «Telegram-бот»."
            )
            return
        if not self._acquire_lock():
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="telegram-poll")
        if self._reminders_enabled():
            self._reminder_task = asyncio.create_task(
                self._reminder_loop(), name="telegram-reminders"
            )
        audit.log_action("telegram_start", f"ids={len(self.allowed_ids())}")

    async def stop(self) -> None:
        self._stop.set()
        for task in (self._task, self._reminder_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._task = None
        self._reminder_task = None
        self._client = None
        self._release_lock()

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    # --- HTTP к Telegram ---
    async def _api(
        self,
        method: str,
        payload: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        if self._client is None:
            raise RuntimeError("Telegram client is not running")
        last_exc: Exception | None = None
        for attempt in range(API_RETRIES):
            try:
                if files:
                    resp = await self._client.post(
                        f"/{method}", data=payload or {}, files=files
                    )
                else:
                    resp = await self._client.post(f"/{method}", json=payload or {})
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise RuntimeError(
                        f"Telegram: некорректный ответ ({resp.status_code})"
                    ) from exc
                if not data.get("ok"):
                    raise RuntimeError(str(data.get("description") or data))
                return data.get("result")
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning(
                    "Telegram %s: сетевая ошибка (%s: %s), попытка %d/%d",
                    method,
                    type(exc).__name__,
                    exc or "нет ответа",
                    attempt + 1,
                    API_RETRIES,
                )
                if attempt + 1 < API_RETRIES:
                    await asyncio.sleep(2 * (attempt + 1))
        raise last_exc if last_exc else RuntimeError("Telegram: нет соединения")

    async def _run(self) -> None:
        token = self.token()
        self._offset = int(settings_store.get("telegram_offset") or 0)
        try:
            async with httpx.AsyncClient(
                base_url=f"{API_BASE}/bot{token}",
                timeout=httpx.Timeout(POLL_TIMEOUT + 15, connect=10),
                limits=self.client_limits(),
                **self.client_options(),
            ) as client:
                self._client = client
                try:
                    me = await self._api("getMe", {})
                    logger.info(
                        "Telegram-бот запущен: @%s (получателей: %d)",
                        me.get("username", "?"),
                        len(self.allowed_ids()),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Telegram-бот: нет доступа к api.telegram.org (%s: %s). "
                        "Проверьте интернет/DNS/прокси в контейнере.",
                        type(exc).__name__,
                        exc,
                    )
                try:
                    await self._api(
                        "setMyCommands",
                        {
                            "commands": [
                                {"command": "start", "description": i18n.t("telegram.cmd_start")},
                                {"command": "help", "description": i18n.t("telegram.cmd_help")},
                                {"command": "reset", "description": i18n.t("telegram.cmd_reset")},
                            ]
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Telegram setMyCommands: %s", exc)
                while not self._stop.is_set():
                    try:
                        updates = await self._api(
                            "getUpdates",
                            {
                                "offset": self._offset,
                                "timeout": POLL_TIMEOUT,
                                "allowed_updates": ["message", "callback_query"],
                            },
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        text = str(exc)
                        if "Conflict" in text:
                            logger.error(
                                "Telegram getUpdates: конфликт опроса — бота опрашивает "
                                "другой процесс/устройство. Остановите лишний экземпляр "
                                "(pgrep -af uvicorn / systemctl status zelvera)."
                            )
                        else:
                            logger.warning(
                                "Telegram getUpdates: %s: %s",
                                type(exc).__name__,
                                exc or "нет ответа от api.telegram.org",
                            )
                        await asyncio.sleep(3)
                        continue
                    for update in updates or []:
                        try:
                            await self._handle_update(update)
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("Telegram: ошибка обработки update")
                            await self._notify_failure(update, exc)
                        self._offset = int(update.get("update_id", 0)) + 1
                        settings_store.update(telegram_offset=str(self._offset))
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            logger.exception("Telegram: цикл опроса остановлен")
        finally:
            self._client = None

    # --- приём сообщений ---
    async def _notify_failure(self, update: dict[str, Any], exc: Exception) -> None:
        """Сообщает пользователю, что обработка не удалась, чтобы не было тишины."""
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            callback = update.get("callback_query") or {}
            chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
        if chat_id is None or chat_id not in self.allowed_ids():
            return
        try:
            await self._send(chat_id, f"{i18n.t('error.prefix')} {exc}")
        except Exception:  # noqa: BLE001
            logger.debug("Telegram: не удалось отправить сообщение об ошибке")

    async def _handle_update(self, update: dict[str, Any]) -> None:
        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
            return
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return
        if chat_id not in self.allowed_ids():
            if not self.allowed_ids():
                await self._send(chat_id, i18n.t("telegram.setup_id", id=chat_id))
            else:
                logger.info("Telegram: доступ запрещён для chat_id=%s", chat_id)
                await self._send(chat_id, i18n.t("telegram.denied"))
            return
        if message.get("voice"):
            await self._handle_voice(chat_id, message)
            return
        if message.get("photo"):
            await self._handle_photo(chat_id, message)
            return
        document = message.get("document") or {}
        mime = str(document.get("mime_type") or "").lower()
        if document and mime.startswith("image/"):
            await self._handle_image(chat_id, document.get("file_id"), mime)
            return
        text = (message.get("text") or "").strip()
        if not text:
            return
        if text.startswith("/"):
            await self._handle_command(chat_id, text)
            return
        answer = await self._answer(chat_id, text)
        await self._send(chat_id, answer)

    async def _handle_command(self, chat_id: int, text: str) -> None:
        command = text.split()[0].split("@")[0].lower()
        if command == "/reset":
            self._history.pop(chat_id, None)
            await self._send(chat_id, i18n.t("telegram.reset"))
        elif command == "/start":
            await self._send(chat_id, i18n.t("telegram.start"))
        else:
            await self._send(chat_id, i18n.t("telegram.help"))

    # --- текстовый чат ---
    async def _answer(self, chat_id: int, text: str) -> str:
        await self._typing(chat_id)
        history = self._history.setdefault(chat_id, [])
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": i18n.t("chat_system")}
        ]
        profile_text = tools.profile_context()
        if profile_text:
            messages.append({"role": "system", "content": profile_text})
        messages.extend(history[-HISTORY_LIMIT:])
        messages.append({"role": "user", "content": text})

        pending_images: list[dict[str, Any]] = []

        async def tool_executor(name: str, arguments: dict) -> str:
            result = await tools.execute_tool(name, arguments)
            for img in kiwix.take_pending_images():
                if img not in pending_images:
                    pending_images.append(img)
            return result

        acc = ""
        try:
            async for chunk in llm.chat_with_tools(
                messages, tools.TOOLS, tool_executor
            ):
                if isinstance(chunk, str):
                    acc += chunk
        except llm.LLMError:
            try:
                async for chunk in llm.stream_chat(messages):
                    acc += chunk
            except llm.LLMError as exc:
                return f"{i18n.t('error.prefix')} {exc}"

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": acc})
        if len(history) > HISTORY_LIMIT:
            del history[:-HISTORY_LIMIT]

        for img in pending_images[:MAX_PENDING_IMAGES]:
            try:
                await self._send_kiwix_image(chat_id, img)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Telegram: не удалось отправить картинку: %s", exc)
        return acc.strip() or i18n.t("telegram.empty_answer")

    # --- фото анализа ---
    async def _handle_photo(self, chat_id: int, message: dict[str, Any]) -> None:
        photos = message.get("photo") or []
        if not photos:
            return
        await self._handle_image(chat_id, photos[-1].get("file_id"), "image/jpeg")

    async def _handle_image(
        self, chat_id: int, file_id: str | None, mime: str
    ) -> None:
        await self._typing(chat_id)
        try:
            data = await self._download_file(file_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram: не удалось скачать фото: %s", exc)
            await self._send(chat_id, i18n.t("telegram.photo_failed"))
            return
        try:
            image_b64 = document.encode_image_bytes(BytesIO(data))
            text = await llm.ocr_image(image_b64, mime or "image/jpeg")
            parsed = await extractor.extract_markers(text)
        except (llm.LLMError, document.DocumentError, ValueError) as exc:
            logger.warning("Telegram: ошибка распознавания: %s", exc)
            await self._send(chat_id, i18n.t("telegram.photo_failed"))
            return

        parsed["markers"] = validation.annotate_markers(parsed.get("markers", []))
        markers = parsed.get("markers") or []
        if not markers:
            await self._send(chat_id, i18n.t("telegram.no_markers"))
            return

        self._pending[chat_id] = {"parsed": parsed, "created": time.time()}
        audit.log_document("telegram", len(markers))
        await self._send(
            chat_id,
            self._render_markers(parsed),
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": i18n.t("telegram.btn_save"), "callback_data": "tg_save"},
                        {"text": i18n.t("telegram.btn_cancel"), "callback_data": "tg_cancel"},
                    ]
                ]
            },
        )

    def _render_markers(self, parsed: dict[str, Any]) -> str:
        markers = parsed.get("markers") or []
        lines = [i18n.t("telegram.analysis_header", n=len(markers))]
        date = parsed.get("date")
        if date:
            lines.append(i18n.t("telegram.analysis_date", date=date))
        for m in markers[:40]:
            value = m.get("value_raw") if m.get("value_raw") is not None else m.get("value")
            unit = m.get("unit") or ""
            status = (m.get("status") or "").lower()
            mark = {"high": " ^", "low": " v"}.get(status, "")
            lines.append(f"- {m.get('name', '')}: {value} {unit}{mark}".rstrip())
        lines.append("")
        lines.append(i18n.t("telegram.analysis_hint"))
        return "\n".join(lines)

    async def _handle_callback(self, callback: dict[str, Any]) -> None:
        chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
        data = callback.get("data") or ""
        callback_id = callback.get("id")
        if chat_id is None or chat_id not in self.allowed_ids():
            return
        message_id = (callback.get("message") or {}).get("message_id")
        if data == "tg_save":
            pending = self._pending.pop(chat_id, None)
            if not pending:
                await self._answer_callback(callback_id, i18n.t("telegram.save_expired"))
                return
            parsed = pending["parsed"]
            try:
                record = database_create_from_telegram(parsed)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Telegram: не удалось сохранить запись")
                await self._answer_callback(callback_id, f"{i18n.t('error.prefix')} {exc}")
                return
            await self._answer_callback(callback_id, i18n.t("telegram.saved"))
            if message_id is not None:
                await self._edit(
                    chat_id,
                    message_id,
                    i18n.t("telegram.saved_record", id=record.get("id", "")),
                    clear_buttons=True,
                )
        elif data == "tg_cancel":
            self._pending.pop(chat_id, None)
            await self._answer_callback(callback_id, i18n.t("telegram.canceled"))
            if message_id is not None:
                await self._edit(
                    chat_id, message_id, i18n.t("telegram.canceled"), clear_buttons=True
                )

    # --- голосовые ---
    async def _handle_voice(self, chat_id: int, message: dict[str, Any]) -> None:
        if not self._voice_enabled() or not voice.stt_available():
            await self._send(chat_id, i18n.t("telegram.voice_disabled"))
            return
        file_id = (message.get("voice") or {}).get("file_id")
        try:
            data = await self._download_file(file_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram: не удалось скачать голосовое: %s", exc)
            await self._send(chat_id, i18n.t("telegram.photo_failed"))
            return
        try:
            text = await voice.transcribe(
                data, settings_store.get("telegram_whisper_model") or "small"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram: ошибка распознавания речи: %s", exc)
            await self._send(chat_id, i18n.t("telegram.voice_failed"))
            return
        if not text.strip():
            await self._send(chat_id, i18n.t("telegram.voice_failed"))
            return
        await self._send(chat_id, i18n.t("telegram.recognized", text=text))
        answer = await self._answer(chat_id, text)
        await self._send(chat_id, answer)
        await self._maybe_send_voice(chat_id, answer)

    async def _maybe_send_voice(self, chat_id: int, text: str) -> None:
        if not self._voice_enabled() or not voice.tts_available():
            return
        try:
            audio = await voice.synthesize(
                text,
                settings_store.get("telegram_tts_voice") or "ru-RU-DmitryNeural",
                proxy=self.proxy(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram: ошибка синтеза речи: %s", exc)
            return
        if not audio:
            return
        try:
            await self._api(
                "sendAudio",
                {"chat_id": chat_id, "title": i18n.t("telegram.voice_title")},
                files={"audio": ("answer.mp3", audio, "audio/mpeg")},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram: не удалось отправить голосовой ответ: %s", exc)

    # --- напоминания ---
    async def _reminder_loop(self) -> None:
        await asyncio.sleep(30)
        while not self._stop.is_set():
            try:
                await self._push_reminders()
            except Exception:  # noqa: BLE001
                logger.exception("Telegram: ошибка рассылки напоминаний")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=REMINDER_INTERVAL)
            except asyncio.TimeoutError:
                continue

    async def _push_reminders(self) -> None:
        if not self._reminders_enabled() or self._client is None:
            return
        try:
            reminders = await asyncio.to_thread(database_list_reminders)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Telegram: напоминания недоступны: %s", exc)
            return
        now = time.time()
        for reminder in reminders:
            days = _days_since(reminder.get("last_reported"))
            if days is None or days < int(reminder.get("interval_days") or 0):
                continue
            key = int(reminder.get("id") or 0)
            if now - self._notified.get(key, 0) < NOTIFY_COOLDOWN:
                continue
            text = i18n.t(
                "telegram.reminder_due",
                marker=reminder.get("marker_name", ""),
                days=days,
                interval=reminder.get("interval_days", ""),
            )
            for chat_id in self.allowed_ids():
                try:
                    await self._send(chat_id, text)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Telegram: напоминание не отправлено: %s", exc)
            self._notified[key] = now

    # --- низкоуровневые отправки ---
    async def _send(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ) -> None:
        parts = split_message(text) or [i18n.t("telegram.empty_answer")]
        for index, part in enumerate(parts):
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": part,
                "disable_web_page_preview": True,
            }
            if reply_markup and index == len(parts) - 1:
                payload["reply_markup"] = reply_markup
            try:
                await self._api("sendMessage", payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telegram sendMessage: %s", exc)
                return

    async def _edit(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        clear_buttons: bool = False,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text[:MESSAGE_LIMIT],
            "disable_web_page_preview": True,
        }
        if clear_buttons:
            payload["reply_markup"] = {"inline_keyboard": []}
        try:
            await self._api("editMessageText", payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Telegram editMessageText: %s", exc)

    async def _answer_callback(self, callback_id: str | None, text: str) -> None:
        if not callback_id:
            return
        try:
            await self._api(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": text[:200]},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Telegram answerCallbackQuery: %s", exc)

    async def _typing(self, chat_id: int) -> None:
        try:
            await self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:  # noqa: BLE001
            pass

    async def _download_file(self, file_id: str | None) -> bytes:
        if not file_id:
            raise ValueError("file_id is empty")
        info = await self._api("getFile", {"file_id": file_id})
        file_path = info.get("file_path")
        if not file_path:
            raise ValueError("file_path is empty")
        token = self.token()
        url = f"{API_BASE}/file/bot{token}/{file_path}"
        async with httpx.AsyncClient(timeout=60, **self.client_options()) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def _send_kiwix_image(self, chat_id: int, img: dict[str, Any]) -> None:
        zim = img.get("zim")
        path = img.get("path")
        if not zim or not path:
            return
        data, _mime = await kiwix.cache_get(zim, path)
        if data is None:
            base = kiwix.get_base_url()
            if not base:
                return
            url = f"{base}/raw/{zim}/content{path}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return
                data = resp.content
        caption = (img.get("caption") or "")[:PHOTO_CAPTION_LIMIT]
        await self._api(
            "sendPhoto",
            {"chat_id": chat_id, "caption": html.unescape(caption)},
            files={"photo": ("image.jpg", data, "image/jpeg")},
        )


def database_list_reminders() -> list[dict[str, Any]]:
    from app.services import database

    return database.list_reminders()


def database_create_from_telegram(parsed: dict[str, Any]) -> dict[str, Any]:
    from app.services import database

    return database.create_record(
        source_name=i18n.t("record.source_telegram"),
        summary=parsed.get("summary", "") or "",
        markers=parsed.get("markers", []),
        date=parsed.get("date"),
        profile_id=tools._current_profile_id(),
    )


bot = TelegramBot()
