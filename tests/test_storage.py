"""Tests for storage.py (task 3: CSV storage)."""
import csv

import pytest

from checkpoint.storage import append_marker


# CSV path derivation

def test_csv_path_derived_from_mkv(tmp_path):
    """CSV path uses same stem + _markers.csv for .mkv input."""
    video = tmp_path / "obs_2024.mkv"
    append_marker(str(video), 0, "test", "")
    expected = tmp_path / "obs_2024_markers.csv"
    assert expected.exists()


def test_csv_path_derived_from_mp4(tmp_path):
    """CSV path uses same stem + _markers.csv for .mp4 input."""
    video = tmp_path / "recording.mp4"
    append_marker(str(video), 0, "test", "")
    expected = tmp_path / "recording_markers.csv"
    assert expected.exists()


# Header row creation

def test_creates_header_when_csv_does_not_exist(tmp_path):
    """Creates CSV with correct UTF-8 header row when file does not exist."""
    video = tmp_path / "obs_2024.mkv"
    append_marker(str(video), 0, "desc", "cat")

    csv_path = tmp_path / "obs_2024_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    assert rows[0] == ["file_path", "timestamp_ms", "timestamp_hms", "description", "category"]


def test_no_duplicate_header_when_csv_exists(tmp_path):
    """Does not write header row when CSV already exists."""
    video = tmp_path / "obs_2024.mkv"
    append_marker(str(video), 0, "first", "a")
    append_marker(str(video), 1000, "second", "b")

    csv_path = tmp_path / "obs_2024_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    # header + 2 data rows, no duplicate header
    assert len(rows) == 3
    assert rows[0] == ["file_path", "timestamp_ms", "timestamp_hms", "description", "category"]


# Data row content

def test_data_row_values(tmp_path):
    """Data row contains correct file_path, timestamp_ms, timestamp_hms, description, category."""
    video = tmp_path / "obs_2024.mkv"
    append_marker(str(video), 90500, "highlight", "gameplay")

    csv_path = tmp_path / "obs_2024_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    data = rows[1]
    assert data[0] == str(video)
    assert data[1] == "90500"
    assert data[2] == "00:01:30.500"
    assert data[3] == "highlight"
    assert data[4] == "gameplay"


def test_timestamp_hms_large_hours(tmp_path):
    """timestamp_hms correctly formats 90061000 ms as 25:01:01.000."""
    video = tmp_path / "rec.mkv"
    append_marker(str(video), 90061000, "desc", "cat")

    csv_path = tmp_path / "rec_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    assert rows[1][2] == "25:01:01.000"


def test_timestamp_hms_zero(tmp_path):
    """timestamp_hms correctly formats 0 ms as 00:00:00.000."""
    video = tmp_path / "rec.mkv"
    append_marker(str(video), 0, "desc", "cat")

    csv_path = tmp_path / "rec_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    assert rows[1][2] == "00:00:00.000"


# UTF-8 and quoting

def test_utf8_encoding(tmp_path):
    """CSV is written with UTF-8 encoding (survives non-ASCII characters)."""
    video = tmp_path / "rec.mkv"
    append_marker(str(video), 0, "déjà vu", "catégorie")

    csv_path = tmp_path / "rec_markers.csv"
    content = csv_path.read_text(encoding="utf-8")
    assert "déjà vu" in content
    assert "catégorie" in content


def test_values_with_commas_are_quoted(tmp_path):
    """Values containing commas are properly quoted by the csv module."""
    video = tmp_path / "rec.mkv"
    append_marker(str(video), 0, "a, b, c", "cat")

    csv_path = tmp_path / "rec_markers.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    assert rows[1][3] == "a, b, c"
