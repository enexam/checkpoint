"""Tests for main_window.py - Settings tab (task 3) and Markers tab (task 4)."""
import csv
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
    for child in list(_tk_session_root.winfo_children()):
        if isinstance(child, tk.Toplevel):
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

    open_main_window(tk_root, config, listener, obs, config_path=tmp_path / "config.json", db_path=tmp_path / "markers.db")
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
# Markers tab - helpers
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
# Markers tab - auto-refresh and notification
# ---------------------------------------------------------------------------

def test_recording_combo_triggers_refresh(tk_root, tmp_path):
    """Selecting a recording in the combobox refreshes the treeview automatically."""
    markers = [
        {"file_path": r"C:\rec\a.mkv", "timestamp_ms": 1000, "description": "A", "category": "x"},
        {"file_path": r"C:\rec\b.mkv", "timestamp_ms": 2000, "description": "B", "category": "x"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    combos = _find_comboboxes(win)
    recording_combo = combos[0]
    recording_combo.set(r"C:\rec\a.mkv")
    recording_combo.event_generate("<<ComboboxSelected>>")
    tk_root.update()

    assert len(tree.get_children()) == 1
    assert tree.set(tree.get_children()[0], "description") == "A"


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
# Markers tab - filter by recording
# ---------------------------------------------------------------------------

def test_markers_filter_by_recording(tk_root, tmp_path):
    """Selecting a recording and clicking Refresh filters Treeview to that file."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 5000, "description": "Clip A", "category": "gameplay"},
        {"file_path": r"C:\rec\video2.mkv", "timestamp_ms": 3000, "description": "Clip B", "category": "bug"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    # Set Recording combobox to video1.mkv's full path.
    combos = _find_comboboxes(win)
    recording_combo = combos[0]
    recording_combo.set(r"C:\rec\video1.mkv")

    _click_button(win, "Refresh")
    tk_root.update()

    assert len(tree.get_children()) == 1
    item = tree.get_children()[0]
    assert tree.set(item, "description") == "Clip A"


# ---------------------------------------------------------------------------
# Markers tab - filter by category
# ---------------------------------------------------------------------------

def test_markers_filter_by_category(tk_root, tmp_path):
    """Selecting a category and clicking Refresh filters Treeview to that category."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 5000, "description": "Clip A", "category": "gameplay"},
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 8000, "description": "Clip B", "category": "bug"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    combos = _find_comboboxes(win)
    category_combo = combos[1]
    category_combo.set("bug")

    _click_button(win, "Refresh")
    tk_root.update()

    assert len(tree.get_children()) == 1
    item = tree.get_children()[0]
    assert tree.set(item, "description") == "Clip B"


# ---------------------------------------------------------------------------
# Markers tab - select all / unselect all
# ---------------------------------------------------------------------------

def test_markers_select_all(tk_root, tmp_path):
    """'Select All' selects every visible row in the Treeview."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 1000, "description": "A", "category": "x"},
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 2000, "description": "B", "category": "x"},
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 3000, "description": "C", "category": "x"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    _click_button(win, "Select All")
    assert len(tree.selection()) == 3


def test_markers_unselect_all(tk_root, tmp_path):
    """'Unselect All' clears the selection."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 1000, "description": "A", "category": "x"},
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 2000, "description": "B", "category": "x"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    _click_button(win, "Select All")
    assert len(tree.selection()) == 2

    _click_button(win, "Unselect All")
    assert len(tree.selection()) == 0


# ---------------------------------------------------------------------------
# Markers tab - export to CSV
# ---------------------------------------------------------------------------

def test_markers_export_csv_with_selection(tk_root, tmp_path):
    """'Export to CSV' writes selected rows in the correct schema."""
    markers = [
        {"file_path": r"C:\rec\video1.mkv", "timestamp_ms": 5000, "description": "My clip", "category": "gameplay"},
    ]
    win = _open_with_markers(tk_root, tmp_path, markers)

    _click_button(win, "Select All")

    out_file = str(tmp_path / "export.csv")
    with patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        _click_button(win, "Export to CSV")

    assert (tmp_path / "export.csv").exists()
    with open(out_file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["file_path"] == r"C:\rec\video1.mkv"
    assert row["timestamp_ms"] == "5000"
    assert row["timestamp_hms"] == "00:00:05.000"
    assert row["description"] == "My clip"
    assert row["category"] == "gameplay"


def test_markers_export_csv_empty_selection_shows_warning(tk_root, tmp_path):
    """'Export to CSV' with no rows selected shows a warning and does not open file dialog."""
    win = _open_with_markers(tk_root, tmp_path, [])

    with patch("tkinter.messagebox.showwarning") as mock_warn, \
         patch("tkinter.filedialog.asksaveasfilename") as mock_dialog:
        _click_button(win, "Export to CSV")
        mock_warn.assert_called_once()
        mock_dialog.assert_not_called()


# ---------------------------------------------------------------------------
# Markers tab - set category
# ---------------------------------------------------------------------------

def test_set_category_button_updates_db(tk_root, tmp_path):
    """'Set for Selection' updates the category of selected markers in the DB."""
    from checkpoint.storage import query_markers

    markers = [
        {"file_path": r"C:\rec\v.mkv", "timestamp_ms": 1000, "description": "A", "category": "old"},
        {"file_path": r"C:\rec\v.mkv", "timestamp_ms": 2000, "description": "B", "category": "old"},
    ]
    db_path = tmp_path / "markers.db"
    win = _open_with_markers(tk_root, tmp_path, markers)
    tree = _find_treeview(win)

    # Select only the first row.
    first_item = tree.get_children()[0]
    tree.selection_set([first_item])

    # Set the category combobox to "newcat".
    combos = _find_comboboxes(win)
    set_cat_combo = combos[2]
    set_cat_combo.set("newcat")

    _click_button(win, "Set for Selection")
    tk_root.update()

    rows = query_markers(db_path=db_path)
    cats = {r["description"]: r["category"] for r in rows}
    assert cats["A"] == "newcat"
    assert cats["B"] == "old"


def test_set_category_no_selection_shows_warning(tk_root, tmp_path):
    """'Set for Selection' with nothing selected shows a warning."""
    win = _open_with_markers(tk_root, tmp_path, [])

    with patch("tkinter.messagebox.showwarning") as mock_warn:
        _click_button(win, "Set for Selection")
        mock_warn.assert_called_once()


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
# Markers tab - export to DaVinci Resolve (.edl)
# ---------------------------------------------------------------------------

def test_export_edl_no_selection_shows_warning(tk_root, tmp_path):
    """'Export to DaVinci Resolve (.edl)' with no rows selected shows a warning and opens no dialog."""
    win = _open_with_markers(tk_root, tmp_path, [])

    with patch("tkinter.messagebox.showwarning") as mock_warn, \
         patch("tkinter.filedialog.asksaveasfilename") as mock_save, \
         patch("checkpoint.main_window._ask_edl_options") as mock_ask:
        _click_button(win, "Export to DaVinci Resolve (.edl)")
        mock_warn.assert_called_once()
        mock_save.assert_not_called()
        mock_ask.assert_not_called()


def test_export_edl_single_recording_writes_file(tk_root, tmp_path):
    """Single-recording selection writes one .edl whose content matches markers_to_edl."""
    from checkpoint.resolve_export import markers_to_edl
    from checkpoint.storage import query_markers

    markers_data = [
        {
            "file_path": r"C:\rec\video1.mkv",
            "timestamp_ms": 30000,
            "begin_timestamp_ms": 10000,
            "description": "Clip A",
            "category": "gameplay",
        },
        {
            "file_path": r"C:\rec\video1.mkv",
            "timestamp_ms": 60000,
            "begin_timestamp_ms": 30000,
            "description": "Clip B",
            "category": "bug",
        },
    ]
    db_path = tmp_path / "markers.db"
    win = _open_with_markers(tk_root, tmp_path, markers_data)

    _click_button(win, "Select All")

    out_file = str(tmp_path / "video1.edl")
    with patch("checkpoint.main_window._ask_edl_options", return_value=(60, "01:00:00:00")), \
         patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        _click_button(win, "Export to DaVinci Resolve (.edl)")

    assert (tmp_path / "video1.edl").exists()

    # Re-query markers by id to get begin_timestamp_ms, same as the implementation does.
    all_rows = query_markers(db_path=db_path)
    rows_by_id = {r["id"]: r for r in all_rows}
    group = [rows_by_id[r["id"]] for r in all_rows if r["file_path"] == r"C:\rec\video1.mkv"]

    expected = markers_to_edl(group, fps=60, start_tc="01:00:00:00", title="video1")

    with open(out_file, "r", newline="", encoding="utf-8") as fh:
        actual = fh.read()
    assert actual == expected


def test_export_edl_two_recordings_writes_two_files(tk_root, tmp_path):
    """Multi-recording selection writes one .edl per recording and shows a summary."""
    markers_data = [
        {
            "file_path": r"C:\rec\video1.mkv",
            "timestamp_ms": 30000,
            "begin_timestamp_ms": 10000,
            "description": "Clip A",
            "category": "gameplay",
        },
        {
            "file_path": r"C:\rec\video2.mkv",
            "timestamp_ms": 20000,
            "begin_timestamp_ms": 5000,
            "description": "Clip B",
            "category": "bug",
        },
    ]
    win = _open_with_markers(tk_root, tmp_path, markers_data)
    out_dir = str(tmp_path / "edl_out")
    import os
    os.makedirs(out_dir, exist_ok=True)

    _click_button(win, "Select All")

    with patch("checkpoint.main_window._ask_edl_options", return_value=(60, "01:00:00:00")), \
         patch("tkinter.filedialog.askdirectory", return_value=out_dir), \
         patch("tkinter.messagebox.showinfo") as mock_info:
        _click_button(win, "Export to DaVinci Resolve (.edl)")
        mock_info.assert_called_once()

    assert (tmp_path / "edl_out" / "video1.edl").exists()
    assert (tmp_path / "edl_out" / "video2.edl").exists()


def test_export_edl_persists_fps_to_config(tk_root, tmp_path):
    """The chosen fps is written to config after export."""
    import json

    markers_data = [
        {
            "file_path": r"C:\rec\video1.mkv",
            "timestamp_ms": 30000,
            "begin_timestamp_ms": 10000,
            "description": "Clip",
            "category": "x",
        },
    ]
    config_path = tmp_path / "config.json"
    win = _open_with_markers(tk_root, tmp_path, markers_data)

    _click_button(win, "Select All")

    out_file = str(tmp_path / "video1.edl")
    with patch("checkpoint.main_window._ask_edl_options", return_value=(30, "01:00:00:00")), \
         patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        _click_button(win, "Export to DaVinci Resolve (.edl)")

    # Config file must be written (or already exist) with last_export_fps = 30.
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved.get("last_export_fps") == 30
