"""Tests for config.py and categories.py (task 1: project scaffold)."""
import json
import pytest


# config.py tests

def test_config_creates_file_with_defaults(tmp_path):
    """config.py creates the directory and file with all four default keys."""
    from checkpoint.config import load_config

    config_path = tmp_path / "config.json"
    result = load_config(config_path=config_path)

    assert config_path.exists()
    assert result["obs_host"] == "localhost"
    assert result["obs_port"] == 4455
    assert result["obs_password"] == ""
    assert result["hotkey"] == "ctrl+f9"


def test_config_creates_parent_directory(tmp_path):
    """config.py creates intermediate directories if they do not exist."""
    from checkpoint.config import load_config

    config_path = tmp_path / "Checkpoint" / "config.json"
    load_config(config_path=config_path)

    assert config_path.exists()


def test_config_returns_existing_file(tmp_path):
    """config.py returns all four keys when the file already exists."""
    from checkpoint.config import load_config

    config_path = tmp_path / "config.json"
    existing = {
        "obs_host": "192.168.1.10",
        "obs_port": 9000,
        "obs_password": "secret",
        "hotkey": "<ctrl>+<shift>+x",
    }
    config_path.write_text(json.dumps(existing), encoding="utf-8")

    result = load_config(config_path=config_path)

    assert result["obs_host"] == "192.168.1.10"
    assert result["obs_port"] == 9000
    assert result["obs_password"] == "secret"
    assert result["hotkey"] == "<ctrl>+<shift>+x"


def test_config_all_four_keys_present(tmp_path):
    """load_config() always returns a dict with exactly the four required keys."""
    from checkpoint.config import load_config

    result = load_config(config_path=tmp_path / "config.json")

    assert set(result.keys()) >= {"obs_host", "obs_port", "obs_password", "hotkey"}


# categories.py tests

def test_categories_missing_file_returns_empty(tmp_path):
    """load_categories() returns [] when the file does not exist."""
    from checkpoint.categories import load_categories

    cats_path = tmp_path / "categories.json"
    result = load_categories(cats_path=cats_path)

    assert result == []


def test_categories_round_trip(tmp_path):
    """save_categories then load_categories returns the same list."""
    from checkpoint.categories import load_categories, save_categories

    cats_path = tmp_path / "categories.json"
    original = ["gameplay", "bug", "highlight"]

    save_categories(original, cats_path=cats_path)
    result = load_categories(cats_path=cats_path)

    assert result == original


def test_categories_round_trip_empty_list(tmp_path):
    """save then load of an empty list round-trips correctly."""
    from checkpoint.categories import load_categories, save_categories

    cats_path = tmp_path / "categories.json"

    save_categories([], cats_path=cats_path)
    result = load_categories(cats_path=cats_path)

    assert result == []


def test_categories_creates_parent_directory(tmp_path):
    """save_categories creates intermediate directories if they do not exist."""
    from checkpoint.categories import save_categories

    cats_path = tmp_path / "Checkpoint" / "categories.json"
    save_categories(["a", "b"], cats_path=cats_path)

    assert cats_path.exists()
