# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Изолированная БД для тестов (без сети и реальных данных)."""
    from app.services import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    database.init_db()
    return database
