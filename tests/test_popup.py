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


# Session fixture: one Tk root for all popup tests

@pytest.fixture(scope="session")
def tk_root():
    """Create a single withdrawn Tk root reused across all popup tests."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("No display available for Tk tests")
    yield root
    try:
        root.destroy()
    except Exception:
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
    """show_popup accepts a list[str] and is callable."""
    from checkpoint.popup import show_popup
    sig = inspect.signature(show_popup)
    params = list(sig.parameters.keys())
    assert params == ["known_categories"]


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
    assert result == ("hello world", "gameplay")


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
    assert result == ("my note", "")


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
