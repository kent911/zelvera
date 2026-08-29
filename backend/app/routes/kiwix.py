# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Прокси для контента Kiwix: изображения из ZIM статей для фронтенда."""
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services import kiwix

router = APIRouter()

TIMEOUT = 30.0


@router.get("/kiwix/image")
async def kiwix_image(
    zim: str = Query(..., description="Имя ZIM-книги"),
    path: str = Query(..., description="Путь внутри книги, напр. /I/File.jpg"),
) -> Response:
    base = kiwix.get_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="Kiwix not configured")
    url = f"{base}/raw/{quote(zim, safe='')}/content{quote(path, safe='/')}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    return Response(content=resp.content, media_type=content_type)
