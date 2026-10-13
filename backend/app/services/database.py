# Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app.config import DATA_DIR, DB_PATH

# Сериализует доступ к файлу БД: все соединения открываются под этим локом,
# а восстановление из копии удерживает его, пока подменяет medical.db.
_DB_LOCK = threading.RLock()

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
    sex TEXT DEFAULT NULL,
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
CREATE TABLE IF NOT EXISTS wiki_cache (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER DEFAULT NULL,
    channel TEXT NOT NULL DEFAULT 'web',
    session_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_messages_profile
    ON memory_messages(profile_id, id);
CREATE INDEX IF NOT EXISTS idx_memory_messages_session
    ON memory_messages(session_id, id);
CREATE TABLE IF NOT EXISTS memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER DEFAULT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    evidence TEXT DEFAULT '',
    source TEXT DEFAULT 'chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_facts_profile
    ON memory_facts(profile_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_facts_unique
    ON memory_facts(profile_id, category, key);
CREATE TABLE IF NOT EXISTS memory_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER DEFAULT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    turn_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_summaries_profile
    ON memory_summaries(profile_id, id);
CREATE TABLE IF NOT EXISTS memory_profile (
    profile_id INTEGER PRIMARY KEY,
    content TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


@contextmanager
def exclusive() -> Iterator[None]:
    """Монопольный доступ к БД: пока удерживается, ни один get_conn() не откроет
    файл. Используется при восстановлении из резервной копии, чтобы подмена
    medical.db не совпала с параллельным чтением/записью."""
    with _DB_LOCK:
        yield


def checkpoint() -> None:
    if not Path(DB_PATH).is_file():
        return
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
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
    if "sex" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN sex TEXT DEFAULT NULL")

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
    for table in (
        "memory_messages",
        "memory_facts",
        "memory_summaries",
    ):
        conn.execute(
            f"UPDATE {table} SET profile_id = ? WHERE profile_id IS NULL",
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
    from app.services import marker_catalog
    from app.services.validation import annotate_markers

    created_at = _normalize_date(date) or datetime.now().strftime("%Y-%m-%d %H:%M")
    markers = [
        {**m, "name": marker_catalog.canonical_name(str(m.get("name", "")))}
        if isinstance(m, dict) and (m.get("name") or "").strip()
        else m
        for m in (markers or [])
    ]
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


def _parse_ref_range(text: Any) -> tuple[float | None, float | None]:
    """Разбирает строку референса в числовые границы (нижняя, верхняя).

    Поддерживает "a-b", "<x", ">x". Возвращает (low, high), где None — нет границы.
    """
    if text is None:
        return None, None
    s = str(text).replace(",", ".").replace("–", "-").replace("—", "-").strip()
    if not s:
        return None, None
    m = re.match(r"^[<≤]\s*([0-9]+(?:\.[0-9]+)?)", s)
    if m:
        return None, float(m.group(1))
    m = re.match(r"^[>≥]\s*([0-9]+(?:\.[0-9]+)?)", s)
    if m:
        return float(m.group(1)), None
    nums = [float(x) for x in re.findall(r"[0-9]+(?:\.[0-9]+)?", s)]
    if len(nums) >= 2:
        low, high = min(nums[0], nums[-1]), max(nums[0], nums[-1])
        return low, high
    return None, None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def marker_trends(profile_id: int | None = None) -> list[dict[str, Any]]:
    """Динамика каждого маркера по хронологии записей (только числовые значения)."""
    with get_conn() as conn:
        if profile_id is None:
            rows = conn.execute(
                """
                SELECT r.created_at AS date, m.name, m.value, m.unit, m.reference_range
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
                SELECT r.created_at AS date, m.name, m.value, m.unit, m.reference_range
                FROM markers m
                JOIN records r ON r.id = m.record_id
                WHERE m.value IS NOT NULL
                  AND r.profile_id = ?
                  AND (m.validation IS NULL OR m.validation = '')
                ORDER BY r.created_at, r.id, m.id
                """,
                (profile_id,),
            ).fetchall()

    from app.services import marker_catalog

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["name"]
        entry = marker_catalog.entry_for(name)
        key = entry["key"] if entry else name
        label = entry["name"] if entry else " ".join(name.split())
        group = groups.setdefault(
            key, {"name": label, "unit": row["unit"] or "", "points": []}
        )
        group["points"].append({"date": row["date"], "value": row["value"]})
        lows: list[float] = group.setdefault("_lows", [])
        highs: list[float] = group.setdefault("_highs", [])
        low, high = _parse_ref_range(row["reference_range"])
        if low is not None:
            lows.append(low)
        if high is not None:
            highs.append(high)

    trends: list[dict[str, Any]] = []
    for group in groups.values():
        points = group["points"]
        group["count"] = len(points)
        group["latest"] = points[-1]["value"]
        group["ref_low"] = _median(group.pop("_lows", []))
        group["ref_high"] = _median(group.pop("_highs", []))
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
            "SELECT id, name, birth_year, height_cm, weight_kg, blood_type, sex, created_at "
            "FROM profiles ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def create_profile(
    name: str,
    birth_year: int | None = None,
    height_cm: int | None = None,
    weight_kg: float | None = None,
    blood_type: str | None = None,
    sex: str | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, birth_year, height_cm, weight_kg, blood_type, sex, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                birth_year,
                height_cm,
                weight_kg,
                blood_type,
                sex,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        profile_id = cur.lastrowid
    return get_profile(profile_id)


def get_profile(profile_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, birth_year, height_cm, weight_kg, blood_type, sex, created_at "
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
    sex: str | None = None,
) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE profiles SET name = ?, birth_year = ?, height_cm = ?, weight_kg = ?, "
            "blood_type = ?, sex = ? WHERE id = ?",
            (name, birth_year, height_cm, weight_kg, blood_type, sex, profile_id),
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
    from app.services import marker_catalog

    if not markers:
        return
    keys = {
        marker_catalog.canonical_key(str(m.get("name", "")))
        for m in markers
        if m.get("name")
    }
    keys.discard(None)
    if not keys:
        return
    with get_conn() as conn:
        if profile_id is None:
            rows = conn.execute(
                "SELECT id, marker_name FROM reminders"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, marker_name FROM reminders WHERE profile_id = ?",
                (profile_id,),
            ).fetchall()
        for row in rows:
            rkey = marker_catalog.canonical_key(row["marker_name"])
            if rkey not in keys:
                continue
            conn.execute(
                "UPDATE reminders SET last_reported = ? "
                "WHERE id = ? AND (last_reported IS NULL OR last_reported < ?)",
                (created_at, row["id"], created_at),
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


def add_memory_message(
    role: str,
    content: str,
    profile_id: int | None = None,
    channel: str = "web",
    session_id: str = "",
) -> int:
    text = (content or "").strip()
    if not text:
        return 0
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO memory_messages "
            "(profile_id, channel, session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                profile_id,
                channel or "web",
                session_id or "",
                role,
                text,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        return int(cur.lastrowid or 0)


def trim_memory_messages(profile_id: int | None = None, keep: int = 80) -> None:
    keep_n = max(1, int(keep))
    with get_conn() as conn:
        if profile_id is None:
            conn.execute(
                "DELETE FROM memory_messages WHERE id NOT IN "
                "(SELECT id FROM (SELECT id FROM memory_messages "
                "ORDER BY id DESC LIMIT ?))",
                (keep_n,),
            )
            return
        conn.execute(
            "DELETE FROM memory_messages WHERE profile_id = ? AND id NOT IN "
            "(SELECT id FROM (SELECT id FROM memory_messages WHERE profile_id = ? "
            "ORDER BY id DESC LIMIT ?))",
            (profile_id, profile_id, keep_n),
        )


def list_memory_messages(
    profile_id: int | None = None,
    limit: int = 40,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    if profile_id is None:
        return []
    sql = (
        "SELECT id, profile_id, channel, session_id, role, content, created_at "
        "FROM memory_messages WHERE profile_id = ?"
    )
    args: list[Any] = [profile_id]
    if session_id is not None:
        sql += " AND session_id = ?"
        args.append(session_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in reversed(rows)]


def count_memory_messages(profile_id: int | None = None) -> int:
    if profile_id is None:
        return 0
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM memory_messages WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
    return int(row[0] if row else 0)


def upsert_memory_fact(
    category: str,
    key: str,
    value: str,
    profile_id: int | None = None,
    evidence: str = "",
    source: str = "chat",
) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cat = (category or "other").strip().lower() or "other"
    k = " ".join((key or "").split())
    v = " ".join((value or "").split())
    if not k or not v:
        raise ValueError("empty fact")
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM memory_facts "
            "WHERE profile_id IS ? AND category = ? AND key = ?",
            (profile_id, cat, k),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memory_facts SET value = ?, evidence = ?, source = ?, "
                "updated_at = ? WHERE id = ?",
                (v, evidence or "", source, now, existing["id"]),
            )
            fact_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO memory_facts "
                "(profile_id, category, key, value, evidence, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (profile_id, cat, k, v, evidence or "", source, now, now),
            )
            fact_id = cur.lastrowid
    return get_memory_fact(fact_id)


def get_memory_fact(fact_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, profile_id, category, key, value, evidence, source, "
            "created_at, updated_at FROM memory_facts WHERE id = ?",
            (fact_id,),
        ).fetchone()
    if row is None:
        raise KeyError(fact_id)
    return dict(row)


def list_memory_facts(profile_id: int | None = None) -> list[dict[str, Any]]:
    if profile_id is None:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, profile_id, category, key, value, evidence, source, "
            "created_at, updated_at FROM memory_facts WHERE profile_id = ? "
            "ORDER BY updated_at DESC, id DESC",
            (profile_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def search_memory_facts(
    query: str,
    profile_id: int | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    tokens = [t.lower() for t in re.findall(r"[0-9a-zA-Zа-яА-ЯёЁ]+", query or "") if t]
    facts = list_memory_facts(profile_id)
    if not tokens:
        return facts[: max(1, int(limit))]
    scored: list[tuple[int, dict[str, Any]]] = []
    for fact in facts:
        blob = " ".join(
            [
                str(fact.get("category") or ""),
                str(fact.get("key") or ""),
                str(fact.get("value") or ""),
                str(fact.get("evidence") or ""),
            ]
        ).lower()
        score = sum(1 for tok in tokens if tok in blob)
        if score:
            scored.append((score, fact))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [f for _, f in scored[: max(1, int(limit))]]


def delete_memory_fact(fact_id: int, profile_id: int | None = None) -> bool:
    with get_conn() as conn:
        if profile_id is None:
            cur = conn.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,))
        else:
            cur = conn.execute(
                "DELETE FROM memory_facts WHERE id = ? AND profile_id = ?",
                (fact_id, profile_id),
            )
        return cur.rowcount > 0


def add_memory_summary(
    content: str,
    profile_id: int | None = None,
    session_id: str = "",
    turn_count: int = 0,
) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        raise ValueError("empty summary")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO memory_summaries "
            "(profile_id, session_id, content, turn_count, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                profile_id,
                session_id or "",
                text,
                max(0, int(turn_count)),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        summary_id = cur.lastrowid
    return get_memory_summary(summary_id)


def get_memory_summary(summary_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, profile_id, session_id, content, turn_count, created_at "
            "FROM memory_summaries WHERE id = ?",
            (summary_id,),
        ).fetchone()
    if row is None:
        raise KeyError(summary_id)
    return dict(row)


def list_memory_summaries(
    profile_id: int | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if profile_id is None:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, profile_id, session_id, content, turn_count, created_at "
            "FROM memory_summaries WHERE profile_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (profile_id, max(1, int(limit))),
        ).fetchall()
    return [dict(r) for r in rows]


def get_memory_portrait(profile_id: int | None) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT profile_id, content, updated_at FROM memory_profile "
            "WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
    return dict(row) if row else None


def set_memory_portrait(profile_id: int, content: str) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = (content or "").strip()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memory_profile (profile_id, content, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(profile_id) DO UPDATE SET content = excluded.content, "
            "updated_at = excluded.updated_at",
            (profile_id, text, now),
        )
    portrait = get_memory_portrait(profile_id)
    if portrait is None:
        raise KeyError(profile_id)
    return portrait


def clear_memory(
    profile_id: int | None = None,
    include_messages: bool = True,
) -> None:
    if profile_id is None:
        return
    with get_conn() as conn:
        if include_messages:
            conn.execute(
                "DELETE FROM memory_messages WHERE profile_id = ?", (profile_id,)
            )
        conn.execute("DELETE FROM memory_facts WHERE profile_id = ?", (profile_id,))
        conn.execute(
            "DELETE FROM memory_summaries WHERE profile_id = ?", (profile_id,)
        )
        conn.execute("DELETE FROM memory_profile WHERE profile_id = ?", (profile_id,))
