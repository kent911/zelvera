# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Отправка писем через SMTP из настроек (восстановление пароля)."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.services import i18n, settings_store

SMTP_TIMEOUT = 15


def recovery_email() -> str:
    return (settings_store.get("recovery_email") or "").strip()


def smtp_host() -> str:
    return (settings_store.get("smtp_host") or "").strip()


def is_configured() -> bool:
    return bool(smtp_host() and recovery_email())


def _port() -> int:
    raw = (settings_store.get("smtp_port") or "587").strip()
    try:
        port = int(raw)
    except ValueError:
        return 587
    return port if 1 <= port <= 65535 else 587


def _from_addr() -> str:
    from_addr = (settings_store.get("smtp_from") or "").strip()
    user = (settings_store.get("smtp_user") or "").strip()
    return from_addr or user or recovery_email()


def send_mail(to: str, subject: str, body: str) -> None:
    host = smtp_host()
    if not host:
        raise ValueError("smtp")
    dest = (to or "").strip()
    if not dest:
        raise ValueError("email")
    port = _port()
    user = (settings_store.get("smtp_user") or "").strip()
    password = settings_store.get("smtp_password") or ""
    use_tls = (settings_store.get("smtp_tls") or "1").strip() != "0"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_addr()
    msg["To"] = dest
    msg.set_content(body)
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(
                host, port, timeout=SMTP_TIMEOUT, context=context
            ) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
            return
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=context)
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        raise ConnectionError(str(exc) or type(exc).__name__) from exc


def send_reset_code(code: str) -> None:
    dest = recovery_email()
    if not dest:
        raise ValueError("email")
    send_mail(
        dest,
        i18n.t("auth.reset_mail_subject"),
        i18n.t("auth.reset_mail_body", code=code),
    )


def send_test() -> None:
    dest = recovery_email()
    if not dest:
        raise ValueError("email")
    if not smtp_host():
        raise ValueError("smtp")
    send_mail(
        dest,
        i18n.t("auth.smtp_test_subject"),
        i18n.t("auth.smtp_test_body"),
    )
