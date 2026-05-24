"""Main application window with Settings and Markers tabs."""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any

from checkpoint.categories import load_categories, save_categories
from checkpoint.config import save_config
from checkpoint.storage import list_categories, list_recordings, query_markers

# Module-level reference to the single open window instance (None when closed).
_window: tk.Toplevel | None = None


def open_main_window(
    root: tk.Tk,
    config: dict,
    hotkey_listener: Any,
    obs_client: Any,
    categories: list[str] | None = None,
    categories_path: Path | None = None,
    config_path: Path | None = None,
    db_path: Path | None = None,
) -> None:
    """Open the main Checkpoint window, or raise it if already open.

    Parameters
    ----------
    root:
        The hidden tk.Tk root that owns the Toplevel.
    config:
        The live application config dict (mutated on Save).
    hotkey_listener:
        The running _HotkeyListener; must expose update_hotkey(str).
    obs_client:
        The running ObsClient; must expose update_config(dict).
    categories_path:
        Optional override for the categories.json path (used in tests).
    config_path:
        Optional override for the config.json path (used in tests).
    db_path:
        Optional override for the markers.db path (used in tests).
    """
    global _window

    # Raise the existing window if it's still alive.
    if _window is not None and _window.winfo_exists():
        _window.deiconify()
        _window.lift()
        _window.focus_force()
        return

    win = tk.Toplevel(root)
    win.title("Checkpoint")
    win.resizable(True, True)
    _window = win

    def _on_close() -> None:
        global _window
        _window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # --- Settings tab ---
    settings_frame = ttk.Frame(notebook)
    notebook.add(settings_frame, text="Settings")

    _build_settings_tab(
        settings_frame,
        config,
        hotkey_listener,
        obs_client,
        live_categories=categories,
        categories_path=categories_path,
        config_path=config_path,
    )

    # --- Markers tab ---
    markers_frame = ttk.Frame(notebook)
    notebook.add(markers_frame, text="Markers")
    _build_markers_tab(markers_frame, db_path=db_path)


def _build_settings_tab(
    parent: ttk.Frame,
    config: dict,
    hotkey_listener: Any,
    obs_client: Any,
    live_categories: list[str] | None,
    categories_path: Path | None,
    config_path: Path | None,
) -> None:
    """Populate the Settings tab with config fields and the categories section."""

    # ------------------------------------------------------------------ #
    # Config fields
    # ------------------------------------------------------------------ #
    fields_frame = ttk.LabelFrame(parent, text="Connection & Hotkey")
    fields_frame.pack(fill="x", padx=8, pady=8)

    ttk.Label(fields_frame, text="Hotkey:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
    hotkey_var = tk.StringVar(value=config.get("hotkey", "ctrl+f9"))
    ttk.Entry(fields_frame, textvariable=hotkey_var, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=4)

    ttk.Label(fields_frame, text="OBS Host:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
    host_var = tk.StringVar(value=config.get("obs_host", "localhost"))
    ttk.Entry(fields_frame, textvariable=host_var, width=20).grid(row=1, column=1, sticky="ew", padx=4, pady=4)

    ttk.Label(fields_frame, text="OBS Port:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
    port_var = tk.StringVar(value=str(config.get("obs_port", 4455)))
    ttk.Spinbox(
        fields_frame,
        textvariable=port_var,
        from_=1,
        to=65535,
        width=8,
    ).grid(row=2, column=1, sticky="w", padx=4, pady=4)

    ttk.Label(fields_frame, text="OBS Password:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
    password_var = tk.StringVar(value=config.get("obs_password", ""))
    ttk.Entry(fields_frame, textvariable=password_var, show="*", width=20).grid(
        row=3, column=1, sticky="ew", padx=4, pady=4
    )

    fields_frame.columnconfigure(1, weight=1)

    def _save() -> None:
        """Validate, persist, and hot-reload the settings."""
        hotkey_str = hotkey_var.get().strip()
        host_str = host_var.get().strip()
        port_str = port_var.get().strip()
        password_str = password_var.get()

        # Validate hotkey by attempting to parse it.
        from checkpoint.app import _parse_hotkey  # imported lazily to avoid circular at module level
        try:
            _parse_hotkey(hotkey_str)
        except ValueError:
            messagebox.showerror("Invalid hotkey", f"Cannot parse hotkey: {hotkey_str!r}")
            return

        # Validate port.
        try:
            port_int = int(port_str)
            if not (1 <= port_int <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid port", f"Port must be an integer between 1 and 65535.")
            return

        # Apply to the shared config dict and persist.
        config["hotkey"] = hotkey_str
        config["obs_host"] = host_str
        config["obs_port"] = port_int
        config["obs_password"] = password_str
        save_config(config, config_path=config_path)

        # Hot-reload hotkey listener and OBS client.
        hotkey_listener.update_hotkey(hotkey_str)
        obs_client.update_config(config)

    ttk.Button(fields_frame, text="Save", command=_save).grid(
        row=4, column=0, columnspan=2, pady=8
    )

    # ------------------------------------------------------------------ #
    # Categories section
    # ------------------------------------------------------------------ #
    cats_frame = ttk.LabelFrame(parent, text="Categories")
    cats_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    listbox = tk.Listbox(cats_frame, selectmode="browse", height=8)
    listbox.pack(fill="both", expand=True, padx=4, pady=4)

    # Populate listbox from file.
    def _reload_listbox() -> None:
        current_cats = load_categories(cats_path=categories_path)
        listbox.delete(0, "end")
        for cat in current_cats:
            listbox.insert("end", cat)

    _reload_listbox()

    add_frame = ttk.Frame(cats_frame)
    add_frame.pack(fill="x", padx=4, pady=(0, 4))

    new_cat_var = tk.StringVar()
    ttk.Entry(add_frame, textvariable=new_cat_var, width=20).pack(side="left", fill="x", expand=True, padx=(0, 4))

    def _add_category() -> None:
        name = new_cat_var.get().strip()
        if not name:
            return
        current_cats = load_categories(cats_path=categories_path)
        if name in current_cats:
            return
        current_cats.append(name)
        save_categories(current_cats, cats_path=categories_path)
        if live_categories is not None and name not in live_categories:
            live_categories.append(name)
        _reload_listbox()
        new_cat_var.set("")

    ttk.Button(add_frame, text="Add", command=_add_category).pack(side="left")


def _build_markers_tab(
    parent: ttk.Frame,
    db_path: Path | None,
) -> None:
    """Populate the Markers tab with filter row, Treeview, and action buttons."""

    # ------------------------------------------------------------------ #
    # Filter row
    # ------------------------------------------------------------------ #
    filter_frame = ttk.Frame(parent)
    filter_frame.pack(fill="x", padx=8, pady=8)

    ttk.Label(filter_frame, text="Recording:").pack(side="left", padx=(0, 4))
    recording_var = tk.StringVar(value="All")
    recording_combo = ttk.Combobox(filter_frame, textvariable=recording_var, state="readonly", width=30)
    recording_combo.pack(side="left", padx=(0, 8))

    ttk.Label(filter_frame, text="Category:").pack(side="left", padx=(0, 4))
    category_var = tk.StringVar(value="All")
    category_combo = ttk.Combobox(filter_frame, textvariable=category_var, state="readonly", width=20)
    category_combo.pack(side="left", padx=(0, 8))

    # ------------------------------------------------------------------ #
    # Treeview - file_path is a hidden column used for export
    # ------------------------------------------------------------------ #
    tree_frame = ttk.Frame(parent)
    tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))

    tree = ttk.Treeview(
        tree_frame,
        columns=("recording", "timestamp", "description", "category", "file_path", "timestamp_ms"),
        displaycolumns=("recording", "timestamp", "description", "category"),
        show="headings",
        selectmode="extended",
    )
    tree.heading("recording", text="Recording")
    tree.heading("timestamp", text="Timestamp")
    tree.heading("description", text="Description")
    tree.heading("category", text="Category")

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # ------------------------------------------------------------------ #
    # Button row
    # ------------------------------------------------------------------ #
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill="x", padx=8, pady=(0, 8))

    def _refresh() -> None:
        """Reload dropdowns and repopulate the Treeview from the DB."""
        # Rebuild recording dropdown.
        recordings = list_recordings(db_path=db_path)
        recording_combo["values"] = ["All"] + recordings

        # Rebuild category dropdown.
        categories = list_categories(db_path=db_path)
        category_combo["values"] = ["All"] + categories

        # Determine filter values.
        rec_filter = recording_var.get()
        file_path_filter: str | None = None if rec_filter == "All" else rec_filter

        cat_filter = category_var.get()
        category_filter: str | None = None if cat_filter == "All" else cat_filter

        # Repopulate Treeview.
        tree.delete(*tree.get_children())
        for row in query_markers(file_path=file_path_filter, category=category_filter, db_path=db_path):
            basename = Path(row["file_path"]).name
            tree.insert(
                "",
                "end",
                values=(
                    basename,
                    row["timestamp_hms"],
                    row["description"],
                    row["category"],
                    row["file_path"],
                    row["timestamp_ms"],
                ),
            )

    ttk.Button(filter_frame, text="Refresh", command=_refresh).pack(side="left")

    def _select_all() -> None:
        tree.selection_set(tree.get_children())

    def _unselect_all() -> None:
        tree.selection_set([])

    def _export_csv() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select at least one row before exporting.")
            return

        out_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export markers to CSV",
        )
        if not out_path:
            return

        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["file_path", "timestamp_ms", "timestamp_hms", "description", "category"])
            for item_id in selected:
                vals = tree.item(item_id, "values")
                # values order: recording(basename), timestamp_hms, description, category, file_path, timestamp_ms
                _recording, timestamp_hms, description, category, file_path, timestamp_ms = vals
                writer.writerow([file_path, timestamp_ms, timestamp_hms, description, category])

    ttk.Button(btn_frame, text="Select All", command=_select_all).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Unselect All", command=_unselect_all).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Export to CSV", command=_export_csv).pack(side="left")

    # Populate on open.
    _refresh()
