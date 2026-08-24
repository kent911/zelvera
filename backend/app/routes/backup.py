# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
"""Резервное копирование и восстановление всех данных приложения.

Экспорт: GET /api/backup/export  -> ZIP-архив (medical.db, settings.json, chroma/).
Импорт:  POST /api/backup/import -> принять ZIP-архив и восстановить данные.
"""
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.config import CHROMA_DIR, DATA_DIR, DB_PATH
from app.services import audit, database, i18n
from app.services.logger import logger

router = APIRouter()

MAX_BACKUP_BYTES = 500 * 1024 * 1024
BACKUP_FILES = ("medical.db", "settings.json")
BACKUP_DIRS = ("chroma",)


def _current_backup_name() -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"zelvera-backup-{stamp}.zip"


def _add_dir_to_zip(zf: zipfile.ZipFile, src_dir: Path, arc_prefix: str) -> int:
    if not src_dir.is_dir():
        return 0
    count = 0
    for path in sorted(src_dir.rglob("*")):
        if path.is_file():
            zf.write(path, f"{arc_prefix}/{path.relative_to(src_dir).as_posix()}")
            count += 1
    return count


@router.get("/backup/export")
def export_backup() -> FileResponse:
    tmp_dir = Path(tempfile.mkdtemp(prefix="zelvera-backup-"))
    zip_path = tmp_dir / _current_backup_name()
    files_added: list[str] = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in BACKUP_FILES:
            src = DATA_DIR / name
            if src.is_file():
                zf.write(src, name)
                files_added.append(name)
        for name in BACKUP_DIRS:
            src = DATA_DIR / name
            if src.is_dir():
                n = _add_dir_to_zip(zf, src, name)
                if n:
                    files_added.append(f"{name}/ ({n} файлов)")
    if not files_added:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=404, detail=i18n.t("backup.no_data"))
    audit.log_action("backup_export", ", ".join(files_added))
    logger.info("Экспорт резервной копии: %s (%s)", zip_path.name, ", ".join(files_added))
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
        background=BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True),
    )


def _restore_from(zip_path: Path, work_dir: Path) -> list[str]:
    """Восстанавливает данные из ZIP-архива. Возвращает список восстановленного.

    Распаковка идёт во временную папку, затем файлы копируются в DATA_DIR,
    чтобы не повредить ChromaDB при записи поверх живых данных.
    """
    restored: list[str] = []
    extract_dir = work_dir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = {Path(n).as_posix() for n in zf.namelist() if not n.endswith("/")}
        if "medical.db" not in names:
            raise HTTPException(
                status_code=400,
                detail=i18n.t("backup.not_a_backup"),
            )
        zf.extractall(str(extract_dir))

    db_src = extract_dir / "medical.db"
    if db_src.is_file():
        shutil.copy2(db_src, DB_PATH)
        restored.append("medical.db")

    settings_src = extract_dir / "settings.json"
    if settings_src.is_file():
        shutil.copy2(settings_src, DATA_DIR / "settings.json")
        restored.append("settings.json")

    chroma_src = extract_dir / "chroma"
    if chroma_src.is_dir():
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(chroma_src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(chroma_src)
            dst = CHROMA_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
        restored.append("chroma/")
    return restored


@router.post("/backup/import")
async def import_backup(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail=i18n.t("backup.need_zip"))

    work_dir = Path(tempfile.mkdtemp(prefix="zelvera-import-"))
    zip_path = work_dir / "upload.zip"
    written = 0
    try:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_BACKUP_BYTES:
                raise HTTPException(status_code=413, detail=i18n.t("backup.too_large"))
            with zip_path.open("ab") as fh:
                fh.write(chunk)
    finally:
        await file.close()

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise HTTPException(status_code=400, detail=i18n.t("backup.corrupted"))
        restored = _restore_from(zip_path, work_dir)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=i18n.t("backup.not_zip")) from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    database.init_db()
    audit.log_action("backup_import", ", ".join(restored))
    logger.info("Импорт резервной копии: %s", ", ".join(restored))
    return {"ok": True, "restored": restored}
