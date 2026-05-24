"""SQLite-based marker storage."""
import os
import sqlite3
from pathlib import Path


def _ms_to_hms(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm string. Hours may exceed 23."""
    millis = ms % 1000
    total_seconds = ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _resolve_db_path(db_path: str | Path | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    appdata = os.environ.get("APPDATA", "")
    path = Path(appdata) / "Checkpoint" / "markers.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db(db_path: str | Path | None = None) -> None:
    """Create the DB file and markers table idempotently.

    Also adds `begin_timestamp_ms` and `duration_hint_ms` columns if missing
    (migration for databases created before Phase 3), and backfills any rows
    that have NULL in those columns.
    """
    path = _resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS markers (
                id          INTEGER PRIMARY KEY,
                file_path   TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                timestamp_hms TEXT NOT NULL,
                description TEXT NOT NULL,
                category    TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_markers_file_path ON markers (file_path);
            CREATE INDEX IF NOT EXISTS idx_markers_category ON markers (category);
        """)
        con.commit()
        # Migration: add new columns if they do not exist yet.
        for col in ("begin_timestamp_ms INTEGER", "duration_hint_ms INTEGER"):
            try:
                con.execute(f"ALTER TABLE markers ADD COLUMN {col}")
                con.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
        # Backfill rows created before this migration.
        con.execute(
            "UPDATE markers SET begin_timestamp_ms = timestamp_ms, duration_hint_ms = 0"
            " WHERE begin_timestamp_ms IS NULL"
        )
        con.commit()
    finally:
        con.close()


def append_marker(
    file_path: str,
    timestamp_ms: int,
    description: str,
    category: str,
    begin_timestamp_ms: int,
    duration_hint_ms: int,
    db_path: str | Path | None = None,
) -> None:
    """Insert one marker row into the database."""
    init_db(db_path)
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    try:
        con.execute(
            "INSERT INTO markers"
            " (file_path, timestamp_ms, timestamp_hms, description, category,"
            "  begin_timestamp_ms, duration_hint_ms)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                file_path,
                timestamp_ms,
                _ms_to_hms(timestamp_ms),
                description,
                category,
                begin_timestamp_ms,
                duration_hint_ms,
            ),
        )
        con.commit()
    finally:
        con.close()


def query_markers(
    file_path: str | None = None,
    category: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Return markers as a list of dicts, optionally filtered by file_path and/or category."""
    init_db(db_path)
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM markers"
        params: list = []
        conditions: list[str] = []
        if file_path is not None:
            conditions.append("file_path = ?")
            params.append(file_path)
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        rows = con.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def list_recordings(db_path: str | Path | None = None) -> list[str]:
    """Return distinct file_path values, sorted."""
    init_db(db_path)
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT DISTINCT file_path FROM markers ORDER BY file_path"
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        con.close()


def list_categories(db_path: str | Path | None = None) -> list[str]:
    """Return distinct category values, sorted."""
    init_db(db_path)
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT DISTINCT category FROM markers ORDER BY category"
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        con.close()


def update_marker_boundaries(
    marker_id: int,
    begin_ms: int,
    end_ms: int,
    db_path: str | Path | None = None,
) -> dict | None:
    """Update begin_timestamp_ms, timestamp_ms, and timestamp_hms for one marker.

    Returns the updated row dict, or None if marker_id does not exist.
    """
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            "UPDATE markers"
            " SET begin_timestamp_ms = ?, timestamp_ms = ?, timestamp_hms = ?"
            " WHERE id = ?",
            (begin_ms, end_ms, _ms_to_hms(end_ms), marker_id),
        )
        con.commit()
        if cur.rowcount == 0:
            return None
        row = con.execute("SELECT * FROM markers WHERE id = ?", (marker_id,)).fetchone()
        return dict(row)
    finally:
        con.close()


def update_markers_category(
    marker_ids: list[int],
    category: str,
    db_path: str | Path | None = None,
) -> None:
    """Set the category column for the given marker IDs. No-op if marker_ids is empty."""
    if not marker_ids:
        return
    path = _resolve_db_path(db_path)
    con = sqlite3.connect(path)
    try:
        placeholders = ",".join("?" * len(marker_ids))
        con.execute(
            f"UPDATE markers SET category = ? WHERE id IN ({placeholders})",
            [category, *marker_ids],
        )
        con.commit()
    finally:
        con.close()
