"""CSV-based marker storage."""
import csv
from pathlib import Path

_HEADER = ["file_path", "timestamp_ms", "timestamp_hms", "description", "category"]


def _ms_to_hms(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm string. Hours may exceed 23."""
    millis = ms % 1000
    total_seconds = ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _csv_path(file_path: str) -> Path:
    p = Path(file_path)
    return p.with_name(p.stem + "_markers.csv")


def append_marker(file_path: str, timestamp_ms: int, description: str, category: str) -> None:
    """Append one marker row to the CSV alongside *file_path*.

    Creates the CSV with a header row if it does not yet exist.
    """
    csv_path = _csv_path(file_path)
    write_header = not csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(_HEADER)
        writer.writerow([
            file_path,
            timestamp_ms,
            _ms_to_hms(timestamp_ms),
            description,
            category,
        ])
