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
RESET_TTL_SEC = 15 * 60
RESET_COOLDOWN_SEC = 60
RESET_MAX_TRIES = 5
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_SEC = 15 * 60

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
            "reset_hash": str(raw.get("reset_hash") or "").strip(),
            "reset_exp": str(raw.get("reset_exp") or "").strip(),
            "reset_last": str(raw.get("reset_last") or "").strip(),
            "reset_tries": str(raw.get("reset_tries") or "").strip(),
            "login_fails": str(raw.get("login_fails") or "").strip(),
            "login_lock": str(raw.get("login_lock") or "").strip(),
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
            "reset_hash": "",
            "reset_exp": "",
            "reset_last": "",
            "reset_tries": "",
            "login_fails": "",
            "login_lock": "",
        }
    )
    return {"username": name}


def _lock_remaining_sec() -> int:
    try:
        until = int(_load().get("login_lock") or "0")
    except ValueError:
        return 0
    left = until - int(time.time())
    return left if left > 0 else 0


def lock_remaining_min() -> int:
    left = _lock_remaining_sec()
    if left <= 0:
        return 0
    return max(1, (left + 59) // 60)


def verify_login(username_value: str, password: str) -> bool:
    if not is_configured():
        return False
    data = _load()
    name_ok = hmac.compare_digest(
        (username_value or "").strip(), data.get("username") or ""
    )
    pass_ok = _verify_password(password or "", data.get("password_hash") or "")
    return bool(name_ok and pass_ok)


def attempt_login(username_value: str, password: str) -> bool:
    if not is_configured():
        return False
    if _lock_remaining_sec() > 0:
        raise ValueError("locked")
    data = dict(_load())
    if data.get("login_lock"):
        data["login_lock"] = ""
        data["login_fails"] = ""
        _save(data)
    if verify_login(username_value, password):
        data = dict(_load())
        data["login_fails"] = ""
        data["login_lock"] = ""
        _save(data)
        return True
    try:
        fails = int(_load().get("login_fails") or "0")
    except ValueError:
        fails = 0
    fails += 1
    data = dict(_load())
    data["login_fails"] = str(fails)
    if fails >= LOGIN_MAX_FAILS:
        data["login_lock"] = str(int(time.time()) + LOGIN_LOCK_SEC)
        data["login_fails"] = "0"
        _save(data)
        raise ValueError("locked")
    _save(data)
    return False


def change_password(old_password: str, new_password: str) -> None:
    if not is_configured():
        raise ValueError("missing")
    if not _verify_password(old_password or "", _load().get("password_hash") or ""):
        raise ValueError("old")
    if len(new_password or "") < MIN_PASSWORD_LEN:
        raise ValueError("password")
    data = dict(_load())
    data["password_hash"] = _hash_password(new_password)
    data["secret"] = secrets.token_hex(32)
    data["reset_hash"] = ""
    data["reset_exp"] = ""
    data["reset_tries"] = ""
    data["login_fails"] = ""
    data["login_lock"] = ""
    _save(data)


def recovery_available() -> bool:
    from app.services import mailer

    return is_configured() and mailer.is_configured()


def request_reset() -> None:
    from app.services import mailer

    if not is_configured():
        raise ValueError("missing")
    if not mailer.is_configured():
        raise ValueError("smtp")
    now = int(time.time())
    data = dict(_load())
    try:
        last = int(data.get("reset_last") or "0")
    except ValueError:
        last = 0
    if last and now - last < RESET_COOLDOWN_SEC:
        raise ValueError("rate")
    code = f"{secrets.randbelow(1_000_000):06d}"
    data["reset_hash"] = _hash_password(code)
    data["reset_exp"] = str(now + RESET_TTL_SEC)
    data["reset_last"] = str(now)
    data["reset_tries"] = "0"
    _save(data)
    try:
        mailer.send_reset_code(code)
    except ConnectionError:
        data = dict(_load())
        data["reset_hash"] = ""
        data["reset_exp"] = ""
        data["reset_tries"] = ""
        _save(data)
        raise


def confirm_reset(code: str, new_password: str) -> None:
    if not is_configured():
        raise ValueError("missing")
    if len(new_password or "") < MIN_PASSWORD_LEN:
        raise ValueError("password")
    data = dict(_load())
    stored = data.get("reset_hash") or ""
    try:
        exp = int(data.get("reset_exp") or "0")
    except ValueError:
        exp = 0
    if not stored or exp < int(time.time()):
        raise ValueError("code")
    try:
        tries = int(data.get("reset_tries") or "0")
    except ValueError:
        tries = 0
    if tries >= RESET_MAX_TRIES:
        data["reset_hash"] = ""
        data["reset_exp"] = ""
        data["reset_tries"] = ""
        _save(data)
        raise ValueError("code")
    if not _verify_password((code or "").strip(), stored):
        data["reset_tries"] = str(tries + 1)
        if tries + 1 >= RESET_MAX_TRIES:
            data["reset_hash"] = ""
            data["reset_exp"] = ""
        _save(data)
        raise ValueError("code")
    data["password_hash"] = _hash_password(new_password)
    data["secret"] = secrets.token_hex(32)
    data["reset_hash"] = ""
    data["reset_exp"] = ""
    data["reset_tries"] = ""
    data["login_fails"] = ""
    data["login_lock"] = ""
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
        "recovery": recovery_available(),
    }
