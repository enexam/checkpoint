"""Tests for main_window.py - Settings tab (task 3)."""
import json
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def tk_root():
    """Provide a hidden tk.Tk root; destroy after the test."""
    root = tk.Tk()
    root.withdraw()
    yield root
    # Reset the module-level _window reference before destroying root so that
    # any Toplevel created during the test is cleaned up properly.
    import checkpoint.main_window as mw
    mw._window = None
    try:
        root.destroy()
    except tk.TclError:
        pass


def _make_listener(hotkey_str: str = "ctrl+f9") -> MagicMock:
    listener = MagicMock()
    listener.hotkey_str = hotkey_str
    return listener


def _make_obs() -> MagicMock:
    return MagicMock()


def _default_config() -> dict:
    return {
        "hotkey": "ctrl+f9",
        "obs_host": "localhost",
        "obs_port": 4455,
        "obs_password": "",
    }


# ---------------------------------------------------------------------------
# open / re-raise
# ---------------------------------------------------------------------------

def test_open_creates_toplevel(tk_root, tmp_path):
    """open_main_window creates a Toplevel child of root."""
    from checkpoint.main_window import open_main_window
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=tmp_path / "config.json")
    children = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(children) == 1


def test_open_twice_raises_existing(tk_root, tmp_path):
    """Calling open_main_window a second time does not open a second Toplevel."""
    from checkpoint.main_window import open_main_window
    config_path = tmp_path / "config.json"
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=config_path)
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=config_path)
    children = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(children) == 1


def test_settings_tab_shows_current_config(tk_root, tmp_path):
    """Settings tab entry widgets reflect the config values passed on open."""
    from checkpoint.main_window import open_main_window
    config = {
        "hotkey": "ctrl+f8",
        "obs_host": "192.168.1.10",
        "obs_port": 4444,
        "obs_password": "secret",
    }
    open_main_window(tk_root, config, _make_listener(), _make_obs(), config_path=tmp_path / "config.json")
    # Drive the event loop briefly so the window is fully rendered.
    tk_root.update()

    # Inspect StringVars by reading entry widgets via winfo_children traversal.
    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    # Collect all Entry and Spinbox widget values from the window hierarchy.
    values = _collect_entry_values(win)
    assert "ctrl+f8" in values
    assert "192.168.1.10" in values
    assert "4444" in values


def _collect_entry_values(widget) -> list[str]:
    """Recursively gather the get() values of all Entry/Spinbox widgets."""
    results = []
    if isinstance(widget, (tk.Entry, tk.Spinbox)):
        try:
            results.append(widget.get())
        except tk.TclError:
            pass
    for child in widget.winfo_children():
        results.extend(_collect_entry_values(child))
    return results


# ---------------------------------------------------------------------------
# Save - valid inputs
# ---------------------------------------------------------------------------

def test_save_valid_writes_config_json(tk_root, tmp_path):
    """Save with valid inputs writes config.json with updated values."""
    from checkpoint.main_window import open_main_window, _build_settings_tab
    from tkinter import ttk

    config = _default_config()
    config_path = tmp_path / "config.json"
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=config_path)
    tk_root.update()

    # Simulate setting a new hotkey by directly manipulating StringVars via
    # the window's widgets and invoking the Save button.
    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_entry_value(win, 0, "ctrl+f8")   # hotkey entry (index among entries)
    _set_entry_value(win, 1, "10.0.0.1")  # host entry
    _set_spinbox_value(win, "9000")        # port spinbox
    _click_button(win, "Save")

    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["hotkey"] == "ctrl+f8"
    assert saved["obs_host"] == "10.0.0.1"
    assert saved["obs_port"] == 9000


def test_save_valid_calls_update_hotkey(tk_root, tmp_path):
    """Save with valid inputs calls hotkey_listener.update_hotkey with the new hotkey."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=tmp_path / "config.json")
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_entry_value(win, 0, "ctrl+f10")
    _click_button(win, "Save")

    listener.update_hotkey.assert_called_once_with("ctrl+f10")


def test_save_valid_calls_update_config_on_obs(tk_root, tmp_path):
    """Save with valid inputs calls obs_client.update_config."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=tmp_path / "config.json")
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _click_button(win, "Save")

    obs.update_config.assert_called_once()


# ---------------------------------------------------------------------------
# Save - invalid hotkey
# ---------------------------------------------------------------------------

def test_save_invalid_hotkey_shows_error(tk_root, tmp_path):
    """Save with an unparseable hotkey shows an error and does not write config."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    config_path = tmp_path / "config.json"
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=config_path)
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_entry_value(win, 0, "INVALID_HOTKEY")

    with patch("tkinter.messagebox.showerror") as mock_err:
        _click_button(win, "Save")
        mock_err.assert_called_once()

    assert not config_path.exists()
    listener.update_hotkey.assert_not_called()
    obs.update_config.assert_not_called()


# ---------------------------------------------------------------------------
# Save - invalid port
# ---------------------------------------------------------------------------

def test_save_invalid_port_shows_error(tk_root, tmp_path):
    """Save with an out-of-range port shows an error and does not write config."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    config_path = tmp_path / "config.json"
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=config_path)
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_spinbox_value(win, "99999")

    with patch("tkinter.messagebox.showerror") as mock_err:
        _click_button(win, "Save")
        mock_err.assert_called_once()

    assert not config_path.exists()
    listener.update_hotkey.assert_not_called()
    obs.update_config.assert_not_called()


def test_save_non_integer_port_shows_error(tk_root, tmp_path):
    """Save with a non-integer port string shows an error."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    config_path = tmp_path / "config.json"
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=config_path)
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_spinbox_value(win, "notanumber")

    with patch("tkinter.messagebox.showerror") as mock_err:
        _click_button(win, "Save")
        mock_err.assert_called_once()

    assert not config_path.exists()


# ---------------------------------------------------------------------------
# Add category
# ---------------------------------------------------------------------------

def test_add_category_appends_to_json(tk_root, tmp_path):
    """Adding a category via the entry+Add button writes it to categories.json."""
    from checkpoint.main_window import open_main_window

    cats_path = tmp_path / "categories.json"
    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        categories_path=cats_path, config_path=tmp_path / "config.json",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    # The last Entry in the window is the category add entry (after hotkey, host, password).
    entries = _find_widgets(win, tk.Entry)
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "gameplay")
    _click_button(win, "Add")

    assert cats_path.exists()
    cats = json.loads(cats_path.read_text(encoding="utf-8"))
    assert "gameplay" in cats


def test_add_category_updates_listbox(tk_root, tmp_path):
    """Adding a category updates the Listbox immediately."""
    from checkpoint.main_window import open_main_window

    cats_path = tmp_path / "categories.json"
    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        categories_path=cats_path, config_path=tmp_path / "config.json",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    entries = _find_widgets(win, tk.Entry)
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "tutorial")
    _click_button(win, "Add")

    listboxes = _find_widgets(win, tk.Listbox)
    assert len(listboxes) == 1
    items = listboxes[0].get(0, "end")
    assert "tutorial" in items


def test_add_duplicate_category_is_ignored(tk_root, tmp_path):
    """Adding a category that already exists does not create a duplicate."""
    from checkpoint.main_window import open_main_window
    from checkpoint.categories import save_categories

    cats_path = tmp_path / "categories.json"
    save_categories(["gameplay"], cats_path=cats_path)

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        categories_path=cats_path, config_path=tmp_path / "config.json",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    entries = _find_widgets(win, tk.Entry)
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "gameplay")
    _click_button(win, "Add")

    cats = json.loads(cats_path.read_text(encoding="utf-8"))
    assert cats.count("gameplay") == 1


def test_add_blank_category_is_ignored(tk_root, tmp_path):
    """Adding a blank category string does nothing."""
    from checkpoint.main_window import open_main_window

    cats_path = tmp_path / "categories.json"
    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        categories_path=cats_path, config_path=tmp_path / "config.json",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    entries = _find_widgets(win, tk.Entry)
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "   ")
    _click_button(win, "Add")

    assert not cats_path.exists()


# ---------------------------------------------------------------------------
# Widget traversal helpers
# ---------------------------------------------------------------------------

def _find_widgets(widget, widget_type) -> list:
    """Recursively find all widgets of *widget_type* under *widget*."""
    results = []
    if isinstance(widget, widget_type):
        results.append(widget)
    for child in widget.winfo_children():
        results.extend(_find_widgets(child, widget_type))
    return results


def _find_buttons(widget) -> list[tk.Button]:
    """Recursively find all Button and ttk.Button widgets."""
    from tkinter import ttk
    results = []
    if isinstance(widget, (tk.Button, ttk.Button)):
        results.append(widget)
    for child in widget.winfo_children():
        results.extend(_find_buttons(child))
    return results


def _click_button(widget, label: str) -> None:
    """Find a button by its text label and invoke it."""
    for btn in _find_buttons(widget):
        try:
            if btn.cget("text") == label:
                btn.invoke()
                return
        except tk.TclError:
            pass
    raise AssertionError(f"Button {label!r} not found in widget tree")


def _set_entry_value(widget, index: int, value: str) -> None:
    """Set the value of the Nth Entry widget (by traversal order, excluding Spinbox)."""
    from tkinter import ttk
    entries = [w for w in _find_widgets(widget, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox))]
    entries[index].delete(0, "end")
    entries[index].insert(0, value)


def _set_spinbox_value(widget, value: str) -> None:
    """Set the value of the first ttk.Spinbox widget found."""
    from tkinter import ttk
    spinboxes = _find_widgets(widget, ttk.Spinbox)
    spinboxes[0].delete(0, "end")
    spinboxes[0].insert(0, value)
