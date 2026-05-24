"""Popup dialog for stamping a marker.

show_popup(known_categories) blocks until the user confirms or dismisses,
then returns (description, category) or None.
"""
import tkinter as tk
import tkinter.ttk as ttk


def show_popup(known_categories: list[str]) -> tuple[str, str] | None:
    """Display a modal dialog for description + category input.

    Parameters
    ----------
    known_categories:
        List of previously used categories shown as Combobox suggestions.

    Returns
    -------
    (description, category) on OK, None on Cancel or window close.
    Description is guaranteed non-empty; category may be an empty string.
    """
    # Reuse an existing Tk root if one already exists, otherwise create one.
    root = tk._default_root  # type: ignore[attr-defined]
    if root is None:
        root = tk.Tk()
        root.withdraw()

    result: list[tuple[str, str] | None] = [None]

    dialog = tk.Toplevel(root)
    dialog.title("Checkpoint")
    dialog.resizable(False, False)
    dialog.wm_attributes("-topmost", 1)
    dialog.grab_set()

    # Description row
    tk.Label(dialog, text="Description").grid(row=0, column=0, padx=8, pady=(12, 4), sticky="e")
    desc_var = tk.StringVar()
    desc_entry = tk.Entry(dialog, textvariable=desc_var, width=36)
    desc_entry.grid(row=0, column=1, padx=(4, 12), pady=(12, 4), sticky="ew")

    # Category row
    tk.Label(dialog, text="Category").grid(row=1, column=0, padx=8, pady=(4, 4), sticky="e")
    cat_var = tk.StringVar()
    cat_combo = ttk.Combobox(dialog, textvariable=cat_var, values=known_categories, state="normal", width=34)
    cat_combo.grid(row=1, column=1, padx=(4, 12), pady=(4, 4), sticky="ew")

    # Button row
    btn_frame = tk.Frame(dialog)
    btn_frame.grid(row=2, column=0, columnspan=2, pady=(8, 12))

    def _on_ok() -> None:
        desc = desc_var.get().strip()
        if not desc:
            desc_entry.focus_set()
            return
        result[0] = (desc, cat_var.get().strip())
        dialog.destroy()

    def _on_cancel() -> None:
        result[0] = None
        dialog.destroy()

    tk.Button(btn_frame, text="OK", width=10, command=_on_ok).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Cancel", width=10, command=_on_cancel).pack(side="left", padx=6)

    dialog.protocol("WM_DELETE_WINDOW", _on_cancel)

    dialog.focus_force()
    desc_entry.focus_set()

    root.wait_window(dialog)

    return result[0]
