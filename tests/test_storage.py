"""Tests for storage.py (SQLite backend)."""
import sqlite3

import pytest

from checkpoint.storage import (
    append_marker,
    init_db,
    list_categories,
    list_recordings,
    query_markers,
    update_marker_boundaries,
)


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db_creates_table(tmp_path):
    """init_db creates the markers table; calling it twice is idempotent."""
    db = tmp_path / "markers.db"
    init_db(db)
    assert db.exists()
    # Second call must not raise
    init_db(db)


def test_init_db_creates_indexes(tmp_path):
    """init_db creates indexes on file_path and category."""
    db = tmp_path / "markers.db"
    init_db(db)
    con = sqlite3.connect(db)
    names = {row[1] for row in con.execute("PRAGMA index_list('markers')").fetchall()}
    con.close()
    assert "idx_markers_file_path" in names
    assert "idx_markers_category" in names


def test_init_db_creates_new_columns(tmp_path):
    """init_db on a fresh DB creates begin_timestamp_ms and duration_hint_ms columns."""
    db = tmp_path / "markers.db"
    init_db(db)
    con = sqlite3.connect(db)
    cols = {row[1] for row in con.execute("PRAGMA table_info('markers')").fetchall()}
    con.close()
    assert "begin_timestamp_ms" in cols
    assert "duration_hint_ms" in cols


def test_init_db_migration_adds_columns_and_backfills(tmp_path):
    """init_db on an old-schema DB (missing new columns) adds them and backfills rows."""
    db = tmp_path / "markers.db"
    # Create old schema manually, without the new columns.
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE markers (
            id          INTEGER PRIMARY KEY,
            file_path   TEXT NOT NULL,
            timestamp_ms INTEGER NOT NULL,
            timestamp_hms TEXT NOT NULL,
            description TEXT NOT NULL,
            category    TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    con.execute(
        "INSERT INTO markers (file_path, timestamp_ms, timestamp_hms, description, category)"
        " VALUES (?, ?, ?, ?, ?)",
        ("C:/rec.mkv", 5000, "00:00:05.000", "old row", "cat"),
    )
    con.commit()
    con.close()

    # Run migration.
    init_db(db)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM markers").fetchone()
    con.close()
    assert dict(row)["begin_timestamp_ms"] == 5000
    assert dict(row)["duration_hint_ms"] == 0


# ---------------------------------------------------------------------------
# append_marker
# ---------------------------------------------------------------------------

def test_append_marker_inserts_row(tmp_path):
    """append_marker inserts a row retrievable via query_markers."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 5000, "great moment", "gameplay", 0, 30000, db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["file_path"] == "C:/rec.mkv"
    assert row["timestamp_ms"] == 5000
    assert row["description"] == "great moment"
    assert row["category"] == "gameplay"


def test_append_marker_stores_new_fields(tmp_path):
    """append_marker stores begin_timestamp_ms and duration_hint_ms correctly."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 35000, "clip", "gameplay", 5000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["begin_timestamp_ms"] == 5000
    assert rows[0]["duration_hint_ms"] == 30000


def test_append_marker_derives_timestamp_hms(tmp_path):
    """append_marker stores correct timestamp_hms for 90500 ms."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 90500, "highlight", "gameplay", 60500, 30000, db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "00:01:30.500"


def test_append_marker_hms_large_hours(tmp_path):
    """timestamp_hms correctly formats 90061000 ms as 25:01:01.000."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 90061000, "desc", "cat", 90031000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "25:01:01.000"


def test_append_marker_hms_zero(tmp_path):
    """timestamp_hms correctly formats 0 ms as 00:00:00.000."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "desc", "cat", 0, 0, db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "00:00:00.000"


def test_append_marker_multiple_rows(tmp_path):
    """Multiple append_marker calls accumulate rows."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "first", "a", 0, 0, db_path=db)
    append_marker("C:/rec.mkv", 1000, "second", "b", 0, 1000, db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 2


def test_append_marker_utf8(tmp_path):
    """append_marker survives non-ASCII characters in description and category."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "déjà vu", "catégorie", 0, 0, db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["description"] == "déjà vu"
    assert rows[0]["category"] == "catégorie"


def test_append_marker_row_has_id_and_created_at(tmp_path):
    """Inserted row has auto-generated id and created_at columns."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "desc", "cat", 0, 0, db_path=db)
    rows = query_markers(db_path=db)
    assert "id" in rows[0]
    assert "created_at" in rows[0]
    assert rows[0]["id"] == 1


# ---------------------------------------------------------------------------
# query_markers
# ---------------------------------------------------------------------------

def test_query_markers_no_filter_returns_all(tmp_path):
    """query_markers with no filter returns all rows."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", 0, 0, db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", 0, 1000, db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 2


def test_query_markers_includes_new_fields(tmp_path):
    """query_markers returns dicts that include begin_timestamp_ms and duration_hint_ms."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 35000, "clip", "gameplay", 5000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    assert "begin_timestamp_ms" in rows[0]
    assert "duration_hint_ms" in rows[0]
    assert rows[0]["begin_timestamp_ms"] == 5000
    assert rows[0]["duration_hint_ms"] == 30000


def test_query_markers_filter_by_file_path(tmp_path):
    """query_markers filters correctly when file_path is set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", 0, 0, db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", 0, 1000, db_path=db)
    rows = query_markers(file_path="C:/a.mkv", db_path=db)
    assert len(rows) == 1
    assert rows[0]["file_path"] == "C:/a.mkv"


def test_query_markers_filter_by_category(tmp_path):
    """query_markers filters correctly when category is set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", 0, 0, db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", 0, 1000, db_path=db)
    rows = query_markers(category="catB", db_path=db)
    assert len(rows) == 1
    assert rows[0]["category"] == "catB"


def test_query_markers_filter_by_both(tmp_path):
    """query_markers filters correctly when both file_path and category are set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", 0, 0, db_path=db)
    append_marker("C:/a.mkv", 1000, "desc2", "catB", 0, 1000, db_path=db)
    append_marker("C:/b.mkv", 2000, "desc3", "catA", 0, 2000, db_path=db)
    rows = query_markers(file_path="C:/a.mkv", category="catA", db_path=db)
    assert len(rows) == 1
    assert rows[0]["description"] == "desc1"


def test_query_markers_returns_list_of_dicts(tmp_path):
    """query_markers return type is list[dict]."""
    db = tmp_path / "markers.db"
    init_db(db)
    rows = query_markers(db_path=db)
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# list_recordings
# ---------------------------------------------------------------------------

def test_list_recordings_distinct_sorted(tmp_path):
    """list_recordings returns distinct file_path values, sorted."""
    db = tmp_path / "markers.db"
    append_marker("C:/b.mkv", 0, "d", "c", 0, 0, db_path=db)
    append_marker("C:/a.mkv", 0, "d", "c", 0, 0, db_path=db)
    append_marker("C:/b.mkv", 1000, "d2", "c", 0, 1000, db_path=db)
    result = list_recordings(db_path=db)
    assert result == ["C:/a.mkv", "C:/b.mkv"]


def test_list_recordings_empty(tmp_path):
    """list_recordings returns empty list when no markers exist."""
    db = tmp_path / "markers.db"
    init_db(db)
    assert list_recordings(db_path=db) == []


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------

def test_list_categories_distinct_sorted(tmp_path):
    """list_categories returns distinct category values, sorted."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "d", "beta", 0, 0, db_path=db)
    append_marker("C:/rec.mkv", 1000, "d", "alpha", 0, 1000, db_path=db)
    append_marker("C:/rec.mkv", 2000, "d", "beta", 0, 2000, db_path=db)
    result = list_categories(db_path=db)
    assert result == ["alpha", "beta"]


def test_list_categories_empty(tmp_path):
    """list_categories returns empty list when no markers exist."""
    db = tmp_path / "markers.db"
    init_db(db)
    assert list_categories(db_path=db) == []


# ---------------------------------------------------------------------------
# update_markers_category
# ---------------------------------------------------------------------------

def test_update_markers_category(tmp_path):
    """update_markers_category changes the category for specified IDs only."""
    from checkpoint.storage import update_markers_category
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "first", "old", 0, 0, db_path=db)
    append_marker("C:/rec.mkv", 1000, "second", "old", 0, 1000, db_path=db)
    rows = query_markers(db_path=db)
    id1 = rows[0]["id"]

    update_markers_category([id1], "new_cat", db_path=db)

    updated = query_markers(db_path=db)
    by_id = {r["id"]: r for r in updated}
    assert by_id[id1]["category"] == "new_cat"
    assert by_id[rows[1]["id"]]["category"] == "old"


def test_update_markers_category_noop_on_empty(tmp_path):
    """update_markers_category with empty list does nothing."""
    from checkpoint.storage import update_markers_category
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "desc", "original", 0, 0, db_path=db)
    update_markers_category([], "new_cat", db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["category"] == "original"


# ---------------------------------------------------------------------------
# update_marker_boundaries
# ---------------------------------------------------------------------------

def test_update_marker_boundaries_updates_and_returns_row(tmp_path):
    """update_marker_boundaries updates the row and returns the updated dict."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 35000, "clip", "gameplay", 5000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    marker_id = rows[0]["id"]

    result = update_marker_boundaries(marker_id, 10000, 40000, db_path=db)

    assert result is not None
    assert result["begin_timestamp_ms"] == 10000
    assert result["timestamp_ms"] == 40000
    assert result["timestamp_hms"] == "00:00:40.000"


def test_update_marker_boundaries_recomputes_hms_from_end(tmp_path):
    """update_marker_boundaries recomputes timestamp_hms from end_ms, not begin_ms."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 60000, "clip", "cat", 30000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    marker_id = rows[0]["id"]

    result = update_marker_boundaries(marker_id, 0, 90500, db_path=db)

    assert result is not None
    assert result["timestamp_hms"] == "00:01:30.500"


def test_update_marker_boundaries_persists_to_db(tmp_path):
    """update_marker_boundaries change is visible on subsequent query."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 35000, "clip", "gameplay", 5000, 30000, db_path=db)
    rows = query_markers(db_path=db)
    marker_id = rows[0]["id"]

    update_marker_boundaries(marker_id, 10000, 40000, db_path=db)

    updated_rows = query_markers(db_path=db)
    row = updated_rows[0]
    assert row["begin_timestamp_ms"] == 10000
    assert row["timestamp_ms"] == 40000


def test_update_marker_boundaries_not_found_returns_none(tmp_path):
    """update_marker_boundaries returns None for a non-existent marker_id."""
    db = tmp_path / "markers.db"
    init_db(db)

    result = update_marker_boundaries(9999, 0, 5000, db_path=db)

    assert result is None
