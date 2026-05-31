"""Tests for main_window.py - window-level concerns: tabs, Settings, notify."""
import json
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def tk_root(_tk_session_root):
    """Per-test fixture: yields the session root, then destroys any Toplevel children and resets _window."""
    yield _tk_session_root
    import checkpoint.main_window as mw
    mw._window = None
    mw._clips_tab = None
    for child in list(_tk_session_root.winfo_children()):
        try:
            child.destroy()
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
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=tmp_path / "config.json", db_path=tmp_path / "markers.db")
    children = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(children) == 1


def test_open_twice_raises_existing(tk_root, tmp_path):
    """Calling open_main_window a second time does not open a second Toplevel."""
    from checkpoint.main_window import open_main_window
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "markers.db"
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=config_path, db_path=db_path)
    open_main_window(tk_root, _default_config(), _make_listener(), _make_obs(), config_path=config_path, db_path=db_path)
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
    open_main_window(tk_root, config, _make_listener(), _make_obs(), config_path=tmp_path / "config.json", db_path=tmp_path / "markers.db")
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

    open_main_window(tk_root, config, listener, obs, config_path=config_path, db_path=tmp_path / "markers.db")
    tk_root.update()

    # Simulate setting a new hotkey by directly manipulating StringVars via
    # the window's widgets and invoking the Save button.
    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    # ClipsTab adds entries before Settings (including Comboboxes as tk.Entry subclasses):
    # recording_combo(0), keyword(1), min_dur(2), max_dur(3), set_cat_combo(4),
    # begin(5), end(6), then Settings: hotkey(7), host(8), password(9), new_cat(10).
    _set_entry_value(win, 7, "ctrl+f8")   # hotkey entry
    _set_entry_value(win, 8, "10.0.0.1")  # host entry
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

    open_main_window(tk_root, config, listener, obs, config_path=tmp_path / "config.json", db_path=tmp_path / "markers.db")
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_entry_value(win, 7, "ctrl+f10")  # hotkey entry (index 7 after ClipsTab entries)
    _click_button(win, "Save")

    listener.update_hotkey.assert_called_once_with("ctrl+f10")


def test_save_valid_calls_update_config_on_obs(tk_root, tmp_path):
    """Save with valid inputs calls obs_client.update_config."""
    from checkpoint.main_window import open_main_window

    config = _default_config()
    listener = _make_listener()
    obs = _make_obs()

    open_main_window(tk_root, config, listener, obs, config_path=tmp_path / "config.json", db_path=tmp_path / "markers.db")
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

    open_main_window(tk_root, config, listener, obs, config_path=config_path, db_path=tmp_path / "markers.db")
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    _set_entry_value(win, 7, "INVALID_HOTKEY")  # hotkey entry

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

    open_main_window(tk_root, config, listener, obs, config_path=config_path, db_path=tmp_path / "markers.db")
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

    open_main_window(tk_root, config, listener, obs, config_path=config_path, db_path=tmp_path / "markers.db")
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
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    # The last plain Entry (excluding Spinbox and Combobox) is the category add entry.
    from tkinter import ttk
    entries = [w for w in _find_widgets(win, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox))]
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
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    from tkinter import ttk
    entries = [w for w in _find_widgets(win, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox))]
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
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    from tkinter import ttk
    entries = [w for w in _find_widgets(win, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox))]
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
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    from tkinter import ttk
    entries = [w for w in _find_widgets(win, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox))]
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "   ")
    _click_button(win, "Add")

    assert not cats_path.exists()


def test_add_category_updates_live_list(tk_root, tmp_path):
    """Adding a category via the UI also appends it to the live categories list."""
    from checkpoint.main_window import open_main_window

    live = ["existing"]
    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        categories=live,
        categories_path=tmp_path / "categories.json",
        config_path=tmp_path / "config.json",
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    from tkinter import ttk
    entries = [w for w in _find_widgets(win, tk.Entry) if not isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox))]
    cat_entry = entries[-1]
    cat_entry.delete(0, "end")
    cat_entry.insert(0, "newcat")
    _click_button(win, "Add")

    assert "newcat" in live


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


def _find_treeview(widget) -> "ttk.Treeview":
    """Find the first ttk.Treeview under *widget*."""
    from tkinter import ttk
    results = _find_widgets(widget, ttk.Treeview)
    assert results, "No Treeview found"
    return results[0]


def _find_comboboxes(widget) -> list:
    """Find all ttk.Combobox widgets under *widget*."""
    from tkinter import ttk
    return _find_widgets(widget, ttk.Combobox)


# ---------------------------------------------------------------------------
# Markers tab helper
# ---------------------------------------------------------------------------

def _open_with_markers(tk_root, tmp_path, markers: list[dict]) -> tk.Toplevel:
    """Open the main window with a temp DB pre-populated with *markers*."""
    from checkpoint.main_window import open_main_window
    from checkpoint.storage import append_marker

    db_path = tmp_path / "markers.db"
    for m in markers:
        append_marker(
            file_path=m["file_path"],
            timestamp_ms=m["timestamp_ms"],
            description=m["description"],
            category=m["category"],
            begin_timestamp_ms=m.get("begin_timestamp_ms", m["timestamp_ms"]),
            duration_hint_ms=m.get("duration_hint_ms", 0),
            db_path=db_path,
        )

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=db_path,
    )
    tk_root.update()
    return [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]


# ---------------------------------------------------------------------------
# Markers tab - population on open
# ---------------------------------------------------------------------------

def test_markers_tab_populates_on_open(tk_root, tmp_path):
    """Markers tab Treeview shows all DB rows on initial open."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 5000, "description": "First clip", "category": "gameplay"},
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 10000, "description": "Second clip", "category": "bug"},
        {"file_path": r"C:\rec\video2.mkv", "timestamp_ms": 2000, "description": "Third clip", "category": "gameplay"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)
    assert len(tree.get_children()) == 3


def test_markers_tab_empty_db_shows_no_rows(tk_root, tmp_path):
    """Markers tab Treeview is empty when the DB has no markers."""
    win = _open_with_markers(tk_root, tmp_path, [])
    tree = _find_treeview(win)
    assert len(tree.get_children()) == 0


# ---------------------------------------------------------------------------
# Markers tab - notify_new_marker
# ---------------------------------------------------------------------------

def test_notify_new_marker_refreshes_treeview(tk_root, tmp_path):
    """notify_new_marker() repopulates the Markers treeview while the window is open."""
    from checkpoint.main_window import open_main_window, notify_new_marker
    from checkpoint.storage import append_marker

    db_path = tmp_path / "markers.db"
    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=db_path,
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    tree = _find_treeview(win)
    assert len(tree.get_children()) == 0

    append_marker(r"C:\rec\v.mkv", 5000, "New clip", "gameplay", 5000, 0, db_path=db_path)
    notify_new_marker()
    tk_root.update()

    assert len(tree.get_children()) == 1


# ---------------------------------------------------------------------------
# Quit button
# ---------------------------------------------------------------------------

def test_quit_button_calls_root_quit(tk_root, tmp_path):
    """The Quit button in the main window calls root.quit()."""
    from checkpoint.main_window import open_main_window

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    with patch.object(tk_root, "quit") as mock_quit:
        _click_button(win, "Quit")
        mock_quit.assert_called_once()


# ---------------------------------------------------------------------------
# Tab structure
# ---------------------------------------------------------------------------

def test_main_window_has_three_tabs(tk_root, tmp_path):
    """The main window notebook must have exactly three tabs: Markers, Settings, About."""
    from checkpoint.main_window import open_main_window
    from tkinter import ttk

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    notebooks = _find_widgets(win, ttk.Notebook)
    assert notebooks, "No Notebook found in window"
    nb = notebooks[0]
    tab_texts = [nb.tab(t, "text") for t in nb.tabs()]
    assert tab_texts == ["Markers", "Settings", "About"]
    assert len(tab_texts) == 3


def test_about_tab_renders_without_error(tk_root, tmp_path):
    """The About tab must render without raising an exception."""
    from checkpoint.main_window import open_main_window
    from tkinter import ttk

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=tmp_path / "markers.db",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    notebooks = _find_widgets(win, ttk.Notebook)
    nb = notebooks[0]
    # Select the About tab and update.
    for t in nb.tabs():
        if nb.tab(t, "text") == "About":
            nb.select(t)
            break
    tk_root.update()
    # No exception means pass.


def test_initial_tab_about_selects_about(tk_root, tmp_path):
    """open_main_window(..., initial_tab='About') must select the About tab."""
    from checkpoint.main_window import open_main_window
    from tkinter import ttk

    open_main_window(
        tk_root, _default_config(), _make_listener(), _make_obs(),
        config_path=tmp_path / "config.json",
        db_path=tmp_path / "markers.db",
        initial_tab="About",
    )
    tk_root.update()

    win = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    notebooks = _find_widgets(win, ttk.Notebook)
    nb = notebooks[0]
    selected_text = nb.tab(nb.select(), "text")
    assert selected_text == "About"
