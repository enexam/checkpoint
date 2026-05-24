"""Load (and create) the Checkpoint configuration file.

Default location: %APPDATA%\\Checkpoint\\config.json
"""
import json
import os
from pathlib import Path

_DEFAULTS: dict = {
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
    "hotkey": "ctrl+f9",
}


def _default_config_path() -> Path:
    appdata = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Checkpoint" / "config.json"


def load_config(*, config_path: Path | None = None) -> dict:
    """Return the configuration dict.

    If *config_path* does not exist, its parent directories are created and the
    file is written with default values before returning those defaults.
    """
    path = Path(config_path) if config_path is not None else _default_config_path()

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULTS, indent=2), encoding="utf-8")
        return dict(_DEFAULTS)

    return json.loads(path.read_text(encoding="utf-8"))


def save_config(config: dict, *, config_path: Path | None = None) -> None:
    """Write *config* to the configuration file, creating parent directories as needed."""
    path = Path(config_path) if config_path is not None else _default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
