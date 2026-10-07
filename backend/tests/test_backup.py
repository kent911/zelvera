# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import io
import zipfile

import pytest
from fastapi import HTTPException

from app.routes import backup
from app.services import database


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "medical.db")
    monkeypatch.setattr(backup, "DATA_DIR", tmp_path)
    monkeypatch.setattr(backup, "DB_PATH", tmp_path / "medical.db")
    monkeypatch.setattr(backup, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(backup, "MEDIA_DIR", tmp_path / "media")
    database.init_db()


def test_wal_mode_enabled(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with database.get_conn() as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    database.checkpoint()
    assert (tmp_path / "medical.db").is_file()


def test_safe_member_path_rejects_zip_slip(tmp_path):
    dest = tmp_path / "extract"
    dest.mkdir()
    assert backup._safe_member_path("medical.db", dest) == (dest / "medical.db").resolve()
    assert backup._safe_member_path("media/1.png", dest) == (dest / "media" / "1.png").resolve()
    assert backup._safe_member_path("../evil.txt", dest) is None
    assert backup._safe_member_path("/etc/passwd", dest) is None
    assert backup._safe_member_path("media/../../etc/passwd", dest) is None
    assert backup._safe_member_path("..\\evil.txt", dest) is None
    assert backup._safe_member_path("", dest) is None
    assert backup._safe_member_path("chroma/", dest) is None


def test_extract_safe_rejects_traversal(tmp_path):
    zip_path = tmp_path / "bad.zip"
    dest = tmp_path / "extract"
    dest.mkdir()
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("medical.db", b"ok")
        zf.writestr("../evil.txt", b"nope")
    with zipfile.ZipFile(zip_path, "r") as zf:
        with pytest.raises(HTTPException) as exc:
            backup._extract_safe(zf, dest)
    assert exc.value.status_code == 400
    assert not (tmp_path / "evil.txt").exists()


def test_export_includes_media_and_import_replaces(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    media = tmp_path / "media"
    media.mkdir()
    (media / "12.png").write_bytes(b"photo-a")
    chroma = tmp_path / "chroma"
    chroma.mkdir()
    (chroma / "old.bin").write_bytes(b"old-chroma")
    (tmp_path / "settings.json").write_text('{"chat_model": "a"}', encoding="utf-8")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.write(tmp_path / "medical.db", "medical.db")
        zf.writestr("settings.json", '{"chat_model": "restored"}')
        zf.writestr("media/12.png", b"photo-restored")
        zf.writestr("media/99.jpg", b"photo-new")
        zf.writestr("chroma/new.bin", b"new-chroma")
    zip_path = tmp_path / "in.zip"
    zip_path.write_bytes(zip_buf.getvalue())
    work = tmp_path / "work"
    work.mkdir()
    restored = backup._restore_from(zip_path, work)
    assert "medical.db" in restored
    assert "settings.json" in restored
    assert "media/" in restored
    assert "chroma/" in restored
    assert (tmp_path / "media" / "12.png").read_bytes() == b"photo-restored"
    assert (tmp_path / "media" / "99.jpg").read_bytes() == b"photo-new"
    assert (tmp_path / "chroma" / "new.bin").read_bytes() == b"new-chroma"
    assert not (tmp_path / "chroma" / "old.bin").exists()
