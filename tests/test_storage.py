"""Tests for storage.py (SQLite backend)."""
import pytest

from checkpoint.storage import (
    append_marker,
    init_db,
    list_categories,
    list_recordings,
    query_markers,
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
    import sqlite3
    db = tmp_path / "markers.db"
    init_db(db)
    con = sqlite3.connect(db)
    names = {row[1] for row in con.execute("PRAGMA index_list('markers')").fetchall()}
    con.close()
    assert "idx_markers_file_path" in names
    assert "idx_markers_category" in names


# ---------------------------------------------------------------------------
# append_marker
# ---------------------------------------------------------------------------

def test_append_marker_inserts_row(tmp_path):
    """append_marker inserts a row retrievable via query_markers."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 5000, "great moment", "gameplay", db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["file_path"] == "C:/rec.mkv"
    assert row["timestamp_ms"] == 5000
    assert row["description"] == "great moment"
    assert row["category"] == "gameplay"


def test_append_marker_derives_timestamp_hms(tmp_path):
    """append_marker stores correct timestamp_hms for 90500 ms."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 90500, "highlight", "gameplay", db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "00:01:30.500"


def test_append_marker_hms_large_hours(tmp_path):
    """timestamp_hms correctly formats 90061000 ms as 25:01:01.000."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 90061000, "desc", "cat", db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "25:01:01.000"


def test_append_marker_hms_zero(tmp_path):
    """timestamp_hms correctly formats 0 ms as 00:00:00.000."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "desc", "cat", db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["timestamp_hms"] == "00:00:00.000"


def test_append_marker_multiple_rows(tmp_path):
    """Multiple append_marker calls accumulate rows."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "first", "a", db_path=db)
    append_marker("C:/rec.mkv", 1000, "second", "b", db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 2


def test_append_marker_utf8(tmp_path):
    """append_marker survives non-ASCII characters in description and category."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "déjà vu", "catégorie", db_path=db)
    rows = query_markers(db_path=db)
    assert rows[0]["description"] == "déjà vu"
    assert rows[0]["category"] == "catégorie"


def test_append_marker_row_has_id_and_created_at(tmp_path):
    """Inserted row has auto-generated id and created_at columns."""
    db = tmp_path / "markers.db"
    append_marker("C:/rec.mkv", 0, "desc", "cat", db_path=db)
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
    append_marker("C:/a.mkv", 0, "desc1", "catA", db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", db_path=db)
    rows = query_markers(db_path=db)
    assert len(rows) == 2


def test_query_markers_filter_by_file_path(tmp_path):
    """query_markers filters correctly when file_path is set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", db_path=db)
    rows = query_markers(file_path="C:/a.mkv", db_path=db)
    assert len(rows) == 1
    assert rows[0]["file_path"] == "C:/a.mkv"


def test_query_markers_filter_by_category(tmp_path):
    """query_markers filters correctly when category is set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", db_path=db)
    append_marker("C:/b.mkv", 1000, "desc2", "catB", db_path=db)
    rows = query_markers(category="catB", db_path=db)
    assert len(rows) == 1
    assert rows[0]["category"] == "catB"


def test_query_markers_filter_by_both(tmp_path):
    """query_markers filters correctly when both file_path and category are set."""
    db = tmp_path / "markers.db"
    append_marker("C:/a.mkv", 0, "desc1", "catA", db_path=db)
    append_marker("C:/a.mkv", 1000, "desc2", "catB", db_path=db)
    append_marker("C:/b.mkv", 2000, "desc3", "catA", db_path=db)
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
    append_marker("C:/b.mkv", 0, "d", "c", db_path=db)
    append_marker("C:/a.mkv", 0, "d", "c", db_path=db)
    append_marker("C:/b.mkv", 1000, "d2", "c", db_path=db)
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
    append_marker("C:/rec.mkv", 0, "d", "beta", db_path=db)
    append_marker("C:/rec.mkv", 1000, "d", "alpha", db_path=db)
    append_marker("C:/rec.mkv", 2000, "d", "beta", db_path=db)
    result = list_categories(db_path=db)
    assert result == ["alpha", "beta"]


def test_list_categories_empty(tmp_path):
    """list_categories returns empty list when no markers exist."""
    db = tmp_path / "markers.db"
    init_db(db)
    assert list_categories(db_path=db) == []
