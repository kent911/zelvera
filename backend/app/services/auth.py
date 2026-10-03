# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Один локальный пользователь: логин/пароль в data/auth.json, сессия в cookie."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import Request, Response

from app.config import DATA_DIR

AUTH_FILE = DATA_DIR / "auth.json"
COOKIE_NAME = "zelvera_session"
SESSION_DAYS = 30
PBKDF2_ITERATIONS = 210_000
MIN_PASSWORD_LEN = 8
MIN_USERNAME_LEN = 2

_cache: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _cache
    if _cache is None:
        try:
            raw = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        _cache = {
            "username": str(raw.get("username") or "").strip(),
            "password_hash": str(raw.get("password_hash") or "").strip(),
            "secret": str(raw.get("secret") or "").strip(),
        }
    return _cache


def _save(data: dict[str, str]) -> None:
    global _cache
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _cache = dict(data)


def reset_cache() -> None:
    global _cache
    _cache = None


def is_configured() -> bool:
    data = _load()
    return bool(data.get("username") and data.get("password_hash") and data.get("secret"))


def username() -> str:
    return _load().get("username") or ""


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt_hex, hash_hex = stored.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iters),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _secret_bytes() -> bytes:
    secret = _load().get("secret") or ""
    return bytes.fromhex(secret) if secret else b""


def setup(username_value: str, password: str) -> dict[str, str]:
    if is_configured():
        raise ValueError("exists")
    name = (username_value or "").strip()
    if len(name) < MIN_USERNAME_LEN:
        raise ValueError("username")
    if len(password or "") < MIN_PASSWORD_LEN:
        raise ValueError("password")
    _save(
        {
            "username": name,
            "password_hash": _hash_password(password),
            "secret": secrets.token_hex(32),
        }
    )
    return {"username": name}


def verify_login(username_value: str, password: str) -> bool:
    if not is_configured():
        return False
    data = _load()
    name_ok = hmac.compare_digest(
        (username_value or "").strip(), data.get("username") or ""
    )
    pass_ok = _verify_password(password or "", data.get("password_hash") or "")
    return bool(name_ok and pass_ok)


def change_password(old_password: str, new_password: str) -> None:
    if not is_configured():
        raise ValueError("missing")
    if not _verify_password(old_password or "", _load().get("password_hash") or ""):
        raise ValueError("old")
    if len(new_password or "") < MIN_PASSWORD_LEN:
        raise ValueError("password")
    data = dict(_load())
    data["password_hash"] = _hash_password(new_password)
    _save(data)


def make_session_token() -> str:
    exp = int(time.time()) + SESSION_DAYS * 24 * 3600
    payload = f"{username()}:{exp}"
    sig = hmac.new(_secret_bytes(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def session_username(token: str | None) -> str | None:
    if not token or not is_configured():
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    name, exp_raw, sig = parts
    try:
        exp = int(exp_raw)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    payload = f"{name}:{exp}"
    expected = hmac.new(
        _secret_bytes(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    if not hmac.compare_digest(name, username()):
        return None
    return name


def read_session(request: Request) -> str | None:
    return session_username(request.cookies.get(COOKIE_NAME))


def set_session_cookie(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_session_token(),
        httponly=True,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 3600,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def status(request: Request) -> dict[str, Any]:
    configured = is_configured()
    name = read_session(request) if configured else None
    return {
        "configured": configured,
        "logged_in": bool(name),
        "username": name or "",
    }
