"""Tests for app.py (task 5: main app orchestration)."""
from unittest.mock import MagicMock

import pytest


# Importability

def test_app_module_importable():
    """app.py can be imported without error."""
    import checkpoint.app  # noqa: F401


def test_main_is_callable():
    """main() exists and is callable."""
    from checkpoint.app import main
    assert callable(main)


def test_open_main_window_is_callable():
    """open_main_window() exists and is callable (placeholder for task 3)."""
    from checkpoint.app import open_main_window
    assert callable(open_main_window)


# Icon image

def test_icon_image_is_64x64_rgba():
    """_make_icon_image() returns a 64×64 RGBA PIL image."""
    from checkpoint.app import _make_icon_image
    img = _make_icon_image()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


# Hotkey callback - via _make_hotkey_callback

def _make_mock_obs(snapshot):
    obs = MagicMock()
    obs.get_snapshot.return_value = snapshot
    return obs


def test_hotkey_callback_returns_early_when_no_snapshot():
    """Callback does nothing when get_snapshot() returns None."""
    from checkpoint.app import _make_hotkey_callback

    obs = _make_mock_obs(None)
    show_popup = MagicMock()
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    show_popup.assert_not_called()
    append_marker.assert_not_called()
    save_cats.assert_not_called()


def test_hotkey_callback_returns_early_when_popup_cancelled():
    """Callback does nothing when show_popup() returns None."""
    from checkpoint.app import _make_hotkey_callback

    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 1000})
    show_popup = MagicMock(return_value=None)
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_not_called()
    save_cats.assert_not_called()


def test_hotkey_callback_appends_marker_on_happy_path():
    """Callback calls append_marker with correct args when popup returns a result."""
    from checkpoint.app import _make_hotkey_callback

    snapshot = {"file_path": "C:/rec.mkv", "timestamp_ms": 5000}
    obs = _make_mock_obs(snapshot)
    show_popup = MagicMock(return_value=("great moment", "gameplay"))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_called_once_with("C:/rec.mkv", 5000, "great moment", "gameplay")


def test_hotkey_callback_appends_new_category_and_saves():
    """Callback adds a new non-empty category to the list and calls save_cats."""
    from checkpoint.app import _make_hotkey_callback

    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", "newcat"))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = ["existing"]

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    assert "newcat" in categories
    save_cats.assert_called_once_with(categories)


def test_hotkey_callback_does_not_duplicate_existing_category():
    """Callback does not add a category that is already in the list."""
    from checkpoint.app import _make_hotkey_callback

    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", "existing"))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = ["existing"]

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    assert categories.count("existing") == 1
    save_cats.assert_not_called()


def test_hotkey_callback_empty_category_does_not_save():
    """Callback does not call save_cats when the returned category is empty."""
    from checkpoint.app import _make_hotkey_callback

    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", ""))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_called_once()
    save_cats.assert_not_called()
    assert categories == []
