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


def _make_cb(obs, categories, show_popup_mock, append_marker_mock, save_cats_mock,
             config=None, save_config_mock=None):
    from checkpoint.app import _make_hotkey_callback
    if config is None:
        config = {"last_duration_preset": "30s"}
    if save_config_mock is None:
        save_config_mock = MagicMock()
    return _make_hotkey_callback(
        obs, categories, show_popup_mock, append_marker_mock, save_cats_mock,
        config, save_config_mock,
    )


def test_hotkey_callback_returns_early_when_no_snapshot():
    """Callback does nothing when get_snapshot() returns None."""
    obs = _make_mock_obs(None)
    show_popup = MagicMock()
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    show_popup.assert_not_called()
    append_marker.assert_not_called()
    save_cats.assert_not_called()


def test_hotkey_callback_returns_early_when_popup_cancelled():
    """Callback does nothing when show_popup() returns None."""
    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 1000})
    show_popup = MagicMock(return_value=None)
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_not_called()
    save_cats.assert_not_called()


def test_hotkey_callback_appends_marker_on_happy_path():
    """Callback calls append_marker with correct begin_ms and duration_hint_ms."""
    snapshot = {"file_path": "C:/rec.mkv", "timestamp_ms": 5000}
    obs = _make_mock_obs(snapshot)
    # popup returns 3-tuple: (description, category, duration_hint_ms)
    show_popup = MagicMock(return_value=("great moment", "gameplay", 30_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    # begin_ms = max(0, 5000 - 30000) = 0
    append_marker.assert_called_once_with("C:/rec.mkv", 5000, "great moment", "gameplay", 0, 30_000)


def test_hotkey_callback_begin_ms_clamped_to_zero():
    """begin_ms is clamped to 0 when end_ms < duration_hint_ms."""
    snapshot = {"file_path": "C:/rec.mkv", "timestamp_ms": 1000}
    obs = _make_mock_obs(snapshot)
    show_popup = MagicMock(return_value=("note", "", 30_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_called_once_with("C:/rec.mkv", 1000, "note", "", 0, 30_000)


def test_hotkey_callback_begin_ms_computed_correctly():
    """begin_ms = end_ms - duration_hint_ms when result >= 0."""
    snapshot = {"file_path": "C:/rec.mkv", "timestamp_ms": 60_000}
    obs = _make_mock_obs(snapshot)
    show_popup = MagicMock(return_value=("note", "", 10_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_called_once_with("C:/rec.mkv", 60_000, "note", "", 50_000, 10_000)


def test_hotkey_callback_persists_preset_to_config():
    """Callback writes last_duration_preset back to config after a successful marker."""
    snapshot = {"file_path": "C:/rec.mkv", "timestamp_ms": 60_000}
    obs = _make_mock_obs(snapshot)
    show_popup = MagicMock(return_value=("note", "", 60_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    save_config = MagicMock()
    config = {"last_duration_preset": "30s"}
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats, config, save_config)
    cb()

    assert config["last_duration_preset"] == "1m"
    save_config.assert_called_once_with(config)


def test_hotkey_callback_appends_new_category_and_saves():
    """Callback adds a new non-empty category to the list and calls save_cats."""
    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", "newcat", 30_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = ["existing"]

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    assert "newcat" in categories
    save_cats.assert_called_once_with(categories)


def test_hotkey_callback_does_not_duplicate_existing_category():
    """Callback does not add a category that is already in the list."""
    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", "existing", 30_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = ["existing"]

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    assert categories.count("existing") == 1
    save_cats.assert_not_called()


def test_hotkey_callback_empty_category_does_not_save():
    """Callback does not call save_cats when the returned category is empty."""
    obs = _make_mock_obs({"file_path": "C:/rec.mkv", "timestamp_ms": 0})
    show_popup = MagicMock(return_value=("note", "", 30_000))
    append_marker = MagicMock()
    save_cats = MagicMock()
    categories = []

    cb = _make_cb(obs, categories, show_popup, append_marker, save_cats)
    cb()

    append_marker.assert_called_once()
    save_cats.assert_not_called()
    assert categories == []


# notify_fn tests

def test_hotkey_callback_calls_notify_fn_when_no_snapshot():
    """When get_snapshot() returns None and notify_fn is provided, it is called once."""
    from checkpoint.app import _make_hotkey_callback
    obs = _make_mock_obs(None)
    show_popup = MagicMock()
    append_marker = MagicMock()
    save_cats = MagicMock()
    notify_fn = MagicMock()

    cb = _make_hotkey_callback(
        obs, [], show_popup, append_marker, save_cats,
        {"last_duration_preset": "30s"}, MagicMock(),
        notify_fn=notify_fn,
    )
    cb()

    notify_fn.assert_called_once_with("Checkpoint", "OBS is not recording")
    show_popup.assert_not_called()
    append_marker.assert_not_called()


def test_hotkey_callback_no_notify_fn_no_error_when_no_snapshot():
    """When get_snapshot() returns None and notify_fn is None, no error occurs."""
    obs = _make_mock_obs(None)
    show_popup = MagicMock()
    append_marker = MagicMock()
    save_cats = MagicMock()

    cb = _make_cb(obs, [], show_popup, append_marker, save_cats)
    cb()  # Must not raise

    show_popup.assert_not_called()
    append_marker.assert_not_called()


# Systray menu tests

def test_build_menu_contains_about_and_report_a_bug():
    """_build_menu returns a pystray.Menu with 'About' and 'Report a Bug' items."""
    from checkpoint.app import _build_menu
    menu = _build_menu(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    labels = [item.text for item in menu]
    assert "About" in labels
    assert "Report a Bug" in labels


def test_build_menu_item_order():
    """_build_menu items are ordered: Open Checkpoint, About, Report a Bug, Quit."""
    from checkpoint.app import _build_menu
    menu = _build_menu(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    labels = [item.text for item in menu]
    assert labels == ["Open Checkpoint", "About", "Report a Bug", "Quit"]
