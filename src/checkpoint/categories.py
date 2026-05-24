"""Persist the list of known marker categories.

Default location: %APPDATA%\\Checkpoint\\categories.json
"""
import json
import os
from pathlib import Path


def _default_cats_path() -> Path:
    appdata = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Checkpoint" / "categories.json"


def load_categories(*, cats_path: Path | None = None) -> list[str]:
    """Return the list of known categories, or [] if the file does not exist."""
    path = Path(cats_path) if cats_path is not None else _default_cats_path()

    if not path.exists():
        return []

    return json.loads(path.read_text(encoding="utf-8"))


def save_categories(cats: list[str], *, cats_path: Path | None = None) -> None:
    """Write *cats* to the categories file, creating parent directories as needed."""
    path = Path(cats_path) if cats_path is not None else _default_cats_path()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cats, indent=2), encoding="utf-8")
