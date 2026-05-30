"""Tests for popup.py (task 3: popup dialog).

Tkinter dialogs need a display. Tests drive interactions by scheduling
callbacks via root.after() before the blocking show_popup() call runs
the event loop.

A session-scoped fixture creates and withdraws a single Tk root for all
popup tests. This avoids the "can't create a second Tk after the first is
destroyed" issue present on some Python/Tcl installations.
"""
import inspect
import tkinter as tk
import tkinter.ttk as ttk
import pytest


@pytest.fixture()
def tk_root(_tk_session_root):
    """Per-test fixture: yields the shared session root, then destroys any Toplevel children."""
    yield _tk_session_root
    for child in list(_tk_session_root.winfo_children()):
        if isinstance(child, tk.Toplevel):
            try:
                child.destroy()
            except tk.TclError:
                pass


# Helpers

def _get_toplevel(root: tk.Tk) -> tk.Toplevel | None:
    """Return the first Toplevel child of root, or None."""
    children = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    return children[0] if children else None


def _find_entry(dialog: tk.Toplevel) -> tk.Entry | None:
    """Return the first Entry widget in the dialog (searches one level deep)."""
    for w in dialog.winfo_children():
        if isinstance(w, tk.Entry):
            return w
        for ww in w.winfo_children():
            if isinstance(ww, tk.Entry):
                return ww
    return None


def _find_button(dialog: tk.Toplevel, text: str) -> tk.Button | None:
    """Return the first Button whose text matches (case-insensitive)."""
    for w in dialog.winfo_children():
        if isinstance(w, tk.Button) and w.cget("text").lower() == text.lower():
            return w
        for ww in w.winfo_children():
            if isinstance(ww, tk.Button) and ww.cget("text").lower() == text.lower():
                return ww
    return None


def _find_combobox(dialog: tk.Toplevel) -> ttk.Combobox | None:
    """Return the first Combobox in the dialog."""
    for w in dialog.winfo_children():
        if isinstance(w, ttk.Combobox):
            return w
        for ww in w.winfo_children():
            if isinstance(ww, ttk.Combobox):
                return ww
    return None


# importability + signature (no Tk needed)

def test_popup_module_importable():
    """popup.py can be imported without error."""
    import checkpoint.popup  # noqa: F401


def test_show_popup_callable_with_correct_signature():
    """show_popup accepts known_categories and an optional initial_preset."""
    from checkpoint.popup import show_popup
    sig = inspect.signature(show_popup)
    params = list(sig.parameters.keys())
    assert params == ["known_categories", "initial_preset"]


# Dialog visibility regression: must not be transient to a withdrawn root

def test_dialog_not_transient_to_withdrawn_root(tk_root):
    """Dialog must not be set transient to the withdrawn root window.

    On Windows, a Toplevel that is transient to a withdrawn (hidden) window is
    itself hidden - it is created and blocks event processing but never appears
    on screen. Removing dialog.transient(root) fixes this.
    """
    from checkpoint.popup import show_popup

    transient_parent: list[str] = ["<not_set>"]

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        transient_parent[0] = dialog.transient()  # "" means no transient relationship
        btn = _find_button(dialog, "Cancel")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    show_popup([])

    assert transient_parent[0] == "", (
        "dialog.transient() returned a non-empty master; on Windows this makes "
        "the dialog invisible when the master window is withdrawn"
    )


# Cancel returns None

def test_cancel_returns_none(tk_root):
    """Clicking Cancel returns None."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        btn = _find_button(dialog, "Cancel")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is None


# Window-close (WM_DELETE_WINDOW) returns None

def test_window_close_returns_none(tk_root):
    """Closing the window (X button) returns None."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        dialog.destroy()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is None


# OK with empty description does NOT close

def test_ok_with_empty_description_does_not_close(tk_root):
    """Clicking OK with an empty description field does not close the dialog."""
    from checkpoint.popup import show_popup

    closed_on_empty: list[bool] = [False]

    def _step1():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _step1)
            return
        entry = _find_entry(dialog)
        if entry:
            entry.delete(0, "end")  # ensure empty
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()
        # Schedule a check: dialog must still exist
        tk_root.after(50, _step2)

    def _step2():
        dialog = _get_toplevel(tk_root)
        if dialog is not None and dialog.winfo_exists():
            closed_on_empty[0] = False  # still open - correct
        else:
            closed_on_empty[0] = True   # closed - wrong
        # Cancel to let show_popup return
        if dialog is not None and dialog.winfo_exists():
            btn = _find_button(dialog, "Cancel")
            if btn:
                btn.invoke()

    tk_root.after(80, _step1)
    result = show_popup([])

    assert closed_on_empty[0] is False
    assert result is None


# OK with description filled returns (description, category)

def test_ok_with_description_returns_tuple(tk_root):
    """OK with non-empty description returns (description.strip(), category.strip())."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        entry = _find_entry(dialog)
        if entry:
            entry.insert(0, "  hello world  ")
        combo = _find_combobox(dialog)
        if combo:
            combo.set("  gameplay  ")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup(["gameplay", "bug"])
    assert result is not None
    assert result[0] == "hello world"
    assert result[1] == "gameplay"
    assert len(result) == 3


# Category can be empty string

def test_ok_with_empty_category_returns_empty_string(tk_root):
    """OK with non-empty description and no category returns (desc, '')."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        entry = _find_entry(dialog)
        if entry:
            entry.insert(0, "my note")
        # leave category empty
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is not None
    assert result[0] == "my note"
    assert result[1] == ""
    assert len(result) == 3


# known_categories appear in combobox values

def test_combobox_has_known_categories(tk_root):
    """The Combobox values include the known_categories passed in."""
    from checkpoint.popup import show_popup

    combo_values: list = [None]

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        combo = _find_combobox(dialog)
        if combo:
            combo_values[0] = combo.cget("values")
        btn = _find_button(dialog, "Cancel")
        if btn:
            btn.invoke()

    cats = ["gameplay", "bug", "highlight"]
    tk_root.after(80, _drive)
    show_popup(cats)

    assert combo_values[0] is not None
    for cat in cats:
        assert cat in combo_values[0]


# Duration preset helpers

def _find_radiobuttons(dialog: tk.Toplevel) -> list[tk.Radiobutton]:
    """Return all Radiobutton widgets in the dialog (recursive)."""
    result = []
    def _collect(widget):
        for w in widget.winfo_children():
            if isinstance(w, tk.Radiobutton):
                result.append(w)
            _collect(w)
    _collect(dialog)
    return result


# Default preset is 30s

def test_default_duration_is_30s(tk_root):
    """On first run (no preset arg), the 30s radio is selected."""
    from checkpoint.popup import show_popup

    desc_and_duration: list = [None]

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        entry = _find_entry(dialog)
        if entry:
            entry.insert(0, "test")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is not None
    assert result[2] == 30_000


# Preset radio buttons return correct ms values

def test_preset_10s_returns_10000ms(tk_root):
    """Selecting 10s preset returns duration_hint_ms == 10000."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        rbs = _find_radiobuttons(dialog)
        for rb in rbs:
            if rb.cget("text") == "10s":
                rb.invoke()
                break
        entry = _find_entry(dialog)
        if entry:
            entry.insert(0, "test")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is not None
    assert result[2] == 10_000


# initial_preset restores radio selection

def test_initial_preset_1m_is_restored(tk_root):
    """Passing initial_preset='1m' selects 1m and returns 60000ms."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        entry = _find_entry(dialog)
        if entry:
            entry.insert(0, "test")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([], initial_preset="1m")
    assert result is not None
    assert result[2] == 60_000


# Custom preset with valid entry

def _find_all_entries(dialog: tk.Toplevel) -> list[tk.Entry]:
    """Return all plain Entry widgets in the dialog (recursive, excludes Combobox)."""
    entries = []
    def _collect(widget):
        for w in widget.winfo_children():
            if isinstance(w, tk.Entry) and not isinstance(w, ttk.Combobox):
                entries.append(w)
            _collect(w)
    _collect(dialog)
    return entries


def test_custom_preset_valid_entry(tk_root):
    """Custom with a numeric entry returns that value * 1000."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        # Click "Custom" radio
        rbs = _find_radiobuttons(dialog)
        for rb in rbs:
            if rb.cget("text") == "Custom":
                rb.invoke()
                break
        # entries[0] = description, entries[1] = custom seconds
        entries = _find_all_entries(dialog)
        if len(entries) >= 2:
            entries[1].delete(0, "end")
            entries[1].insert(0, "45")
        if entries:
            entries[0].delete(0, "end")
            entries[0].insert(0, "test")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is not None
    assert result[2] == 45_000


# Custom preset with empty entry falls back to 30000ms

def test_custom_preset_empty_entry_fallback(tk_root):
    """Custom with empty entry falls back to 30000ms."""
    from checkpoint.popup import show_popup

    def _drive():
        dialog = _get_toplevel(tk_root)
        if dialog is None:
            tk_root.after(30, _drive)
            return
        rbs = _find_radiobuttons(dialog)
        for rb in rbs:
            if rb.cget("text") == "Custom":
                rb.invoke()
                break
        entries = _find_all_entries(dialog)
        if len(entries) >= 2:
            entries[1].delete(0, "end")  # leave empty
        if entries:
            entries[0].delete(0, "end")
            entries[0].insert(0, "test")
        btn = _find_button(dialog, "OK")
        if btn:
            btn.invoke()

    tk_root.after(80, _drive)
    result = show_popup([])
    assert result is not None
    assert result[2] == 30_000
