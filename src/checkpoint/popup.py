"""Popup dialog for stamping a marker.

show_popup(known_categories, initial_preset) blocks until the user confirms or
dismisses, then returns (description, category, duration_hint_ms) or None.
"""
import tkinter as tk
import tkinter.ttk as ttk

from checkpoint.resources import set_window_icon

_PRESET_MS: dict[str, int] = {
    "10s": 10_000,
    "30s": 30_000,
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
}
_PRESET_LABELS = ["10s", "30s", "1m", "3m", "5m", "Custom"]


def show_popup(
    known_categories: list[str],
    initial_preset: str = "30s",
) -> tuple[str, str, int] | None:
    """Display a modal dialog for description + category + duration input.

    Parameters
    ----------
    known_categories:
        List of previously used categories shown as Combobox suggestions.
    initial_preset:
        The preset to select on open. One of "10s", "30s", "1m", "3m", "5m",
        or a "custom:N" string (N is seconds). Defaults to "30s".

    Returns
    -------
    (description, category, duration_hint_ms) on OK, None on Cancel or window
    close. Description is guaranteed non-empty; category may be an empty string.
    For Custom with an empty or invalid entry, duration_hint_ms is 30000.
    """
    # Reuse an existing Tk root if one already exists, otherwise create one.
    root = tk._default_root  # type: ignore[attr-defined]
    if root is None:
        root = tk.Tk()
        root.withdraw()

    result: list[tuple[str, str, int] | None] = [None]

    dialog = tk.Toplevel(root)
    dialog.title("Checkpoint")
    dialog.resizable(False, False)
    set_window_icon(dialog)
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

    # Duration row
    tk.Label(dialog, text="Duration").grid(row=2, column=0, padx=8, pady=(4, 4), sticky="ne")

    dur_frame = tk.Frame(dialog)
    dur_frame.grid(row=2, column=1, padx=(4, 12), pady=(4, 4), sticky="w")

    # Parse initial_preset to determine which radio to select and custom value.
    if initial_preset.startswith("custom:"):
        _selected_label = "Custom"
        try:
            _custom_secs = str(int(initial_preset[7:]))
        except ValueError:
            _custom_secs = ""
    elif initial_preset in _PRESET_MS:
        _selected_label = initial_preset
        _custom_secs = ""
    else:
        _selected_label = "30s"
        _custom_secs = ""

    dur_var = tk.StringVar(value=_selected_label)
    custom_secs_var = tk.StringVar(value=_custom_secs)

    # Place radios in a horizontal layout; the custom seconds Entry follows inline.
    for label in _PRESET_LABELS:
        tk.Radiobutton(dur_frame, text=label, variable=dur_var, value=label).pack(side="left")

    custom_entry = tk.Entry(dur_frame, textvariable=custom_secs_var, width=6)
    custom_entry.pack(side="left", padx=(2, 0))

    # Show or hide the custom entry based on initial state.
    if _selected_label != "Custom":
        custom_entry.pack_forget()

    def _on_preset_change(*_args: object) -> None:
        if dur_var.get() == "Custom":
            custom_entry.pack(side="left", padx=(2, 0))
        else:
            custom_entry.pack_forget()

    # Bind the change handler to each radiobutton.
    for widget in dur_frame.winfo_children():
        if isinstance(widget, tk.Radiobutton):
            widget.configure(command=_on_preset_change)

    # Button row
    btn_frame = tk.Frame(dialog)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=(8, 12))

    def _get_duration_ms() -> int:
        sel = dur_var.get()
        if sel in _PRESET_MS:
            return _PRESET_MS[sel]
        # Custom
        try:
            secs = int(custom_secs_var.get().strip())
            if secs <= 0:
                raise ValueError
            return secs * 1000
        except (ValueError, AttributeError):
            return 30_000

    def _on_ok() -> None:
        desc = desc_var.get().strip()
        if not desc:
            desc_entry.focus_set()
            return
        result[0] = (desc, cat_var.get().strip(), _get_duration_ms())
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
