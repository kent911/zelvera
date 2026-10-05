# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.services import audit, auth, i18n

router = APIRouter()


class SetupIn(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class PasswordChangeIn(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class ResetConfirmIn(BaseModel):
    code: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


@router.get("/auth/status")
async def auth_status(request: Request) -> dict:
    return auth.status(request)


@router.post("/auth/setup")
async def auth_setup(body: SetupIn, response: Response) -> dict:
    try:
        saved = auth.setup(body.username, body.password)
    except ValueError as exc:
        code = str(exc)
        if code == "exists":
            raise HTTPException(status_code=409, detail=i18n.t("auth.exists")) from exc
        if code == "username":
            raise HTTPException(status_code=400, detail=i18n.t("auth.username_short")) from exc
        raise HTTPException(status_code=400, detail=i18n.t("auth.password_short")) from exc
    auth.set_session_cookie(response)
    audit.log_action("auth_setup", saved["username"])
    return {"ok": True, "username": saved["username"]}


@router.post("/auth/login")
async def auth_login(body: LoginIn, response: Response) -> dict:
    try:
        ok = auth.attempt_login(body.username, body.password)
    except ValueError as exc:
        if str(exc) == "locked":
            raise HTTPException(
                status_code=429,
                detail=i18n.t("auth.locked", min=auth.lock_remaining_min()),
            ) from exc
        raise HTTPException(status_code=401, detail=i18n.t("auth.invalid")) from exc
    if not ok:
        raise HTTPException(status_code=401, detail=i18n.t("auth.invalid"))
    auth.set_session_cookie(response)
    audit.log_action("auth_login", auth.username())
    return {"ok": True, "username": auth.username()}


@router.post("/auth/logout")
async def auth_logout(response: Response) -> dict:
    auth.clear_session_cookie(response)
    return {"ok": True}


@router.post("/auth/password")
async def auth_password(body: PasswordChangeIn, request: Request, response: Response) -> dict:
    if not auth.read_session(request):
        raise HTTPException(status_code=401, detail=i18n.t("auth.required"))
    try:
        auth.change_password(body.old_password, body.new_password)
    except ValueError as exc:
        code = str(exc)
        if code == "old":
            raise HTTPException(status_code=400, detail=i18n.t("auth.old_invalid")) from exc
        if code == "missing":
            raise HTTPException(status_code=400, detail=i18n.t("auth.not_configured")) from exc
        raise HTTPException(status_code=400, detail=i18n.t("auth.password_short")) from exc
    auth.set_session_cookie(response)
    audit.log_action("auth_password", auth.username())
    return {"ok": True}


@router.post("/auth/reset/request")
async def auth_reset_request() -> dict:
    try:
        auth.request_reset()
    except ValueError as exc:
        code = str(exc)
        if code == "missing":
            raise HTTPException(status_code=400, detail=i18n.t("auth.not_configured")) from exc
        if code == "rate":
            raise HTTPException(status_code=429, detail=i18n.t("auth.reset_rate")) from exc
        raise HTTPException(status_code=400, detail=i18n.t("auth.reset_no_smtp")) from exc
    except ConnectionError as exc:
        raise HTTPException(
            status_code=502, detail=i18n.t("auth.reset_send_failed", err=exc)
        ) from exc
    audit.log_action("auth_reset_request", auth.username())
    return {"ok": True}


@router.post("/auth/reset/confirm")
async def auth_reset_confirm(body: ResetConfirmIn, response: Response) -> dict:
    try:
        auth.confirm_reset(body.code, body.new_password)
    except ValueError as exc:
        code = str(exc)
        if code == "missing":
            raise HTTPException(status_code=400, detail=i18n.t("auth.not_configured")) from exc
        if code == "password":
            raise HTTPException(status_code=400, detail=i18n.t("auth.password_short")) from exc
        raise HTTPException(status_code=400, detail=i18n.t("auth.reset_invalid")) from exc
    auth.set_session_cookie(response)
    audit.log_action("auth_reset", auth.username())
    return {"ok": True, "username": auth.username()}
