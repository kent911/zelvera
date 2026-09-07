# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from app.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    summary TEXT DEFAULT '',
    profile_id INTEGER DEFAULT NULL,
    image_path TEXT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value REAL,
    value_raw TEXT,
    unit TEXT,
    reference_range TEXT,
    status TEXT,
    validation TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_markers_record ON markers(record_id);
CREATE INDEX IF NOT EXISTS idx_markers_name ON markers(name);
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    summary TEXT DEFAULT '',
    chunk_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_article ON notes(article_id);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birth_year INTEGER DEFAULT NULL,
    height_cm INTEGER DEFAULT NULL,
    weight_kg REAL DEFAULT NULL,
    blood_type TEXT DEFAULT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER DEFAULT NULL,
    marker_name TEXT NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 30,
    last_reported TEXT,
    created_at TEXT NOT NULL
);
"""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        _ensure_default_profile(conn)
        _attach_orphan_records(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Добавляет отсутствующие колонки в существующую БД."""
    if "profile_id" not in _columns(conn, "records"):
        conn.execute(
            "ALTER TABLE records ADD COLUMN profile_id INTEGER DEFAULT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_profile ON records(profile_id)"
        )

    profile_cols = _columns(conn, "profiles")
    if "birth_year" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN birth_year INTEGER DEFAULT NULL")
    if "height_cm" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN height_cm INTEGER DEFAULT NULL")
    if "weight_kg" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN weight_kg REAL DEFAULT NULL")
    if "blood_type" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN blood_type TEXT DEFAULT NULL")

    if "validation" not in _columns(conn, "markers"):
        conn.execute("ALTER TABLE markers ADD COLUMN validation TEXT DEFAULT NULL")

    if "image_path" not in _columns(conn, "records"):
        conn.execute("ALTER TABLE records ADD COLUMN image_path TEXT DEFAULT NULL")


def _ensure_default_profile(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()
    if cur[0] == 0:
        conn.execute(
            "INSERT INTO profiles (name, created_at) VALUES (?, ?)",
            ("Мой профиль", datetime.now().strftime("%Y-%m-%d %H:%M")),
        )


def _attach_orphan_records(conn: sqlite3.Connection) -> None:
    """Записи, созданные до появления профилей (profile_id IS NULL),
    привязывает к профилю по умолчанию, чтобы они отображались в карте."""
    row = conn.execute("SELECT MIN(id) AS pid FROM profiles").fetchone()
    default_id = row["pid"] if row and row["pid"] is not None else None
    if default_id is None:
        return
    conn.execute(
        "UPDATE records SET profile_id = ? WHERE profile_id IS NULL",
        (default_id,),
    )
    conn.execute(
        "UPDATE reminders SET profile_id = ? WHERE profile_id IS NULL",
        (default_id,),
    )


def _to_float(value: Any) -> tuple[float | None, str]:
    if value is None:
        return None, ""
    if isinstance(value, int):
        return float(value), str(value)
    if isinstance(value, float):
        if value.is_integer():
            return value, str(int(value))
        return value, str(value)
    text = str(value).replace(",", ".").strip()
    try:
        return float(text), text
    except ValueError:
        return None, text


def _normalize_date(value: Any) -> str | None:
    """Приводит дату к виду ГГГГ-ММ-ДД или возвращает None."""
    if value is None:
        return None
    text = str(value).strip().replace("/", "-").replace(".", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if m:
        y, mo, d = m.groups()
        result = f"{y}-{int(mo):02d}-{int(d):02d}"
    else:
        m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", text)
        if m:
            d, mo, y = m.groups()
            result = f"{y}-{int(mo):02d}-{int(d):02d}"
        else:
            return None
    try:
        datetime.strptime(result, "%Y-%m-%d")
    except ValueError:
        return None
    return result


def create_record(
    source_name: str,
    summary: str,
    markers: list[dict[str, Any]],
    date: str | None = None,
    profile_id: int | None = None,
) -> dict[str, Any]:
    from app.services.validation import annotate_markers

    created_at = _normalize_date(date) or datetime.now().strftime("%Y-%m-%d %H:%M")
    annotated = annotate_markers(markers)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO records (source_name, created_at, summary, profile_id) "
            "VALUES (?, ?, ?, ?)",
            (source_name, created_at, summary, profile_id),
        )
        record_id = cur.lastrowid
        for m in annotated:
            value, value_raw = _to_float(m.get("value"))
            validation = m.get("validation")
            conn.execute(
                "INSERT INTO markers "
                "(record_id, name, value, value_raw, unit, reference_range, status, validation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    str(m.get("name", "")).strip(),
                    value,
                    value_raw,
                    str(m.get("unit", "") or ""),
                    str(m.get("reference_range", "") or ""),
                    str(m.get("status", "unknown")),
                    (validation or {}).get("code"),
                ),
            )
    _update_reminders(markers, created_at, profile_id)
    return get_record(record_id)


def list_records(profile_id: int | None = None) -> list[dict[str, Any]]:
    select = (
        "SELECT id, source_name, created_at, summary, profile_id, image_path, "
        "(SELECT COUNT(*) FROM markers m WHERE m.record_id = r.id) AS marker_count "
        "FROM records r"
    )
    with get_conn() as conn:
        if profile_id is None:
            rows = conn.execute(select + " ORDER BY r.created_at DESC, r.id DESC").fetchall()
        else:
            rows = conn.execute(
                select + " WHERE r.profile_id = ? "
                "ORDER BY r.created_at DESC, r.id DESC",
                (profile_id,),
            ).fetchall()
        return [dict(row) for row in rows]


def set_record_image(record_id: int, image_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE records SET image_path = ? WHERE id = ?",
            (image_path, record_id),
        )


def get_record(record_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source_name, created_at, summary, profile_id, image_path "
            "FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(record_id)
        markers = conn.execute(
            "SELECT name, value, value_raw, unit, reference_range, status, validation "
            "FROM markers WHERE record_id = ? ORDER BY id",
            (record_id,),
        ).fetchall()
        result = dict(row)
        result["markers"] = [dict(m) for m in markers]
        return result


def markers_for_records(record_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Возвращает маркеры для списка записей: {record_id: [marker, ...]}."""
    if not record_ids:
        return {}
    with get_conn() as conn:
        placeholders = ",".join("?" * len(record_ids))
        rows = conn.execute(
            f"SELECT record_id, name, value, value_raw, unit, reference_range, status, validation "
            f"FROM markers WHERE record_id IN ({placeholders}) ORDER BY id",
            record_ids,
        ).fetchall()
    out: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(row["record_id"], []).append(dict(row))
    return out


def delete_record(record_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        return cur.rowcount > 0


def create_article(filename: str, summary: str = "") -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO articles (filename, uploaded_at, summary) VALUES (?, ?, ?)",
            (filename, now, summary),
        )
        return cur.lastrowid


def update_article_summary(article_id: int, summary: str, chunk_count: int = 0) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET summary = ?, chunk_count = ? WHERE id = ?",
            (summary, chunk_count, article_id),
        )


def list_articles() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, uploaded_at, summary, chunk_count "
            "FROM articles ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_article(article_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, filename, uploaded_at, summary, chunk_count "
            "FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()
    if row is None:
        raise KeyError(article_id)
    return dict(row)


def delete_article(article_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        return cur.rowcount > 0


def create_note(article_id: int | None, content: str) -> dict[str, Any]:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO notes (article_id, content, created_at) VALUES (?, ?, ?)",
            (article_id, content, created_at),
        )
        note_id = cur.lastrowid
    return get_note(note_id)


def get_note(note_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, article_id, content, created_at FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    if row is None:
        raise KeyError(note_id)
    return dict(row)


def list_notes() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT n.id, n.article_id, n.content, n.created_at, "
            "COALESCE(a.filename, '') AS filename "
            "FROM notes n "
            "LEFT JOIN articles a ON a.id = n.article_id "
            "ORDER BY n.id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_note(note_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount > 0


def marker_trends(profile_id: int | None = None) -> list[dict[str, Any]]:
    """Динамика каждого маркера по хронологии записей (только числовые значения)."""
    with get_conn() as conn:
        if profile_id is None:
            rows = conn.execute(
                """
                SELECT r.created_at AS date, m.name, m.value, m.unit
                FROM markers m
                JOIN records r ON r.id = m.record_id
                WHERE m.value IS NOT NULL
                  AND (m.validation IS NULL OR m.validation = '')
                ORDER BY r.created_at, r.id, m.id
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.created_at AS date, m.name, m.value, m.unit
                FROM markers m
                JOIN records r ON r.id = m.record_id
                WHERE m.value IS NOT NULL
                  AND r.profile_id = ?
                  AND (m.validation IS NULL OR m.validation = '')
                ORDER BY r.created_at, r.id, m.id
                """,
                (profile_id,),
            ).fetchall()

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["name"]
        group = groups.setdefault(
            name, {"name": name, "unit": row["unit"] or "", "points": []}
        )
        group["points"].append({"date": row["date"], "value": row["value"]})

    trends: list[dict[str, Any]] = []
    for group in groups.values():
        points = group["points"]
        group["count"] = len(points)
        group["latest"] = points[-1]["value"]
        group["trend"] = "single"
        if len(points) >= 2:
            first = points[0]["value"]
            last = points[-1]["value"]
            delta = (last - first) / first * 100 if first else 0.0
            if delta > 1:
                group["trend"] = "up"
            elif delta < -1:
                group["trend"] = "down"
            else:
                group["trend"] = "stable"
        trends.append(group)

    return trends


MAX_AUDIT_DETAIL = 1000


def add_audit(action: str, detail: str = "") -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    detail = (detail or "")[:MAX_AUDIT_DETAIL]
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (created_at, action, detail) VALUES (?, ?, ?)",
            (created_at, action, detail),
        )
        return cur.lastrowid


def list_audit(action: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 5000))
    with get_conn() as conn:
        if action:
            rows = conn.execute(
                "SELECT id, created_at, action, detail FROM audit_log "
                "WHERE action = ? ORDER BY id DESC LIMIT ?",
                (action, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, created_at, action, detail FROM audit_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def audit_actions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT action, COUNT(*) AS count FROM audit_log "
            "GROUP BY action ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def clear_audit() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM audit_log")


def list_profiles() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, birth_year, height_cm, weight_kg, blood_type, created_at "
            "FROM profiles ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def create_profile(
    name: str,
    birth_year: int | None = None,
    height_cm: int | None = None,
    weight_kg: float | None = None,
    blood_type: str | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, birth_year, height_cm, weight_kg, blood_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                name,
                birth_year,
                height_cm,
                weight_kg,
                blood_type,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        profile_id = cur.lastrowid
    return get_profile(profile_id)


def get_profile(profile_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, birth_year, height_cm, weight_kg, blood_type, created_at "
            "FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
    if row is None:
        raise KeyError(profile_id)
    return dict(row)


def update_profile(
    profile_id: int,
    name: str,
    birth_year: int | None = None,
    height_cm: int | None = None,
    weight_kg: float | None = None,
    blood_type: str | None = None,
) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE profiles SET name = ?, birth_year = ?, height_cm = ?, weight_kg = ?, "
            "blood_type = ? WHERE id = ?",
            (name, birth_year, height_cm, weight_kg, blood_type, profile_id),
        )
        return cur.rowcount > 0


def delete_profile(profile_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cur.rowcount > 0


def _update_reminders(
    markers: list[dict[str, Any]], created_at: str, profile_id: int | None
) -> None:
    """Обновляет last_reported у напоминаний, когда появляется новый показатель."""
    if not markers:
        return
    names = [str(m.get("name", "")).strip() for m in markers if m.get("name")]
    if not names:
        return
    with get_conn() as conn:
        for name in names:
            if profile_id is None:
                conn.execute(
                    "UPDATE reminders SET last_reported = ? WHERE marker_name = ? "
                    "AND (last_reported IS NULL OR last_reported < ?)",
                    (created_at, name, created_at),
                )
            else:
                conn.execute(
                    "UPDATE reminders SET last_reported = ? WHERE marker_name = ? "
                    "AND profile_id = ? "
                    "AND (last_reported IS NULL OR last_reported < ?)",
                    (created_at, name, profile_id, created_at),
                )


def create_reminder(
    marker_name: str,
    interval_days: int,
    profile_id: int | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (profile_id, marker_name, interval_days, created_at) "
            "VALUES (?, ?, ?, ?)",
            (profile_id, marker_name, max(1, interval_days), datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        reminder_id = cur.lastrowid
    return get_reminder(reminder_id)


def get_reminder(reminder_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, profile_id, marker_name, interval_days, last_reported, created_at "
            "FROM reminders WHERE id = ?",
            (reminder_id,),
        ).fetchone()
    if row is None:
        raise KeyError(reminder_id)
    return dict(row)


def list_reminders(profile_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if profile_id is None:
            rows = conn.execute(
                "SELECT id, profile_id, marker_name, interval_days, last_reported, created_at "
                "FROM reminders ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, profile_id, marker_name, interval_days, last_reported, created_at "
                "FROM reminders WHERE profile_id = ? ORDER BY id",
                (profile_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def delete_reminder(reminder_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        return cur.rowcount > 0
