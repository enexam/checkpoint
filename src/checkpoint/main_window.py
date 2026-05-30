"""Main application window with Settings and Markers tabs."""
import csv
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any, Callable

from checkpoint.categories import load_categories, save_categories
from checkpoint.config import save_config
from checkpoint import about, resolve_export
from checkpoint.resources import set_window_icon
from checkpoint.storage import delete_marker, list_categories, list_recordings, query_markers, update_markers_category

# Module-level reference to the single open window instance (None when closed).
_window: tk.Toplevel | None = None

# Refresh callback for the Markers tab; set when the tab is built, cleared on close.
_refresh_fn: Callable | None = None

_EDL_FPS_OPTIONS: list[str] = ["24", "25", "30", "50", "60"]


def _ask_edl_options(parent: tk.Misc, initial_fps: int) -> tuple[int, str] | None:
    """Show a small modal dialog to collect EDL export options.

    Parameters
    ----------
    parent:
        Parent window for the modal dialog.
    initial_fps:
        Default fps selection (from config).

    Returns
    -------
    tuple[int, str] or None
        ``(fps, start_tc)`` on OK, ``None`` on cancel.
    """
    result: list[tuple[int, str]] = []

    dialog = tk.Toplevel(parent)
    dialog.title("EDL Export Options")
    dialog.resizable(False, False)
    dialog.grab_set()

    ttk.Label(dialog, text="FPS (must match Resolve timeline):").grid(
        row=0, column=0, sticky="w", padx=8, pady=(8, 2)
    )
    fps_var = tk.StringVar(value=str(initial_fps) if str(initial_fps) in _EDL_FPS_OPTIONS else "60")
    fps_combo = ttk.Combobox(dialog, textvariable=fps_var, values=_EDL_FPS_OPTIONS, state="readonly", width=8)
    fps_combo.grid(row=0, column=1, sticky="w", padx=8, pady=(8, 2))

    ttk.Label(dialog, text="Timeline start TC:").grid(
        row=1, column=0, sticky="w", padx=8, pady=(2, 2)
    )
    tc_var = tk.StringVar(value="01:00:00:00")
    ttk.Entry(dialog, textvariable=tc_var, width=14).grid(row=1, column=1, sticky="w", padx=8, pady=(2, 2))

    ttk.Label(dialog, text="FPS must match your DaVinci Resolve timeline.", foreground="gray").grid(
        row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4)
    )

    btn_frame = ttk.Frame(dialog)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=(0, 8))

    def _ok() -> None:
        result.append((int(fps_var.get()), tc_var.get().strip()))
        dialog.destroy()

    def _cancel() -> None:
        dialog.destroy()

    ttk.Button(btn_frame, text="OK", command=_ok).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side="left", padx=4)

    dialog.wait_window()
    return result[0] if result else None


def notify_new_marker() -> None:
    """Refresh the Markers tab if the main window is currently open."""
    if _refresh_fn is not None:
        _refresh_fn()


def open_main_window(
    root: tk.Tk,
    config: dict,
    hotkey_listener: Any,
    obs_client: Any,
    categories: list[str] | None = None,
    categories_path: Path | None = None,
    config_path: Path | None = None,
    db_path: Path | None = None,
    on_quit: Callable | None = None,
    initial_tab: str | None = None,
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
    initial_tab:
        If not None, selects the notebook tab whose text matches this string after
        all tabs are built. Used by systray menu items to open directly to a tab.
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
    set_window_icon(win)
    _window = win

    def _on_close() -> None:
        global _window, _refresh_fn
        _window = None
        _refresh_fn = None
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
    _build_markers_tab(markers_frame, db_path=db_path, config=config, config_path=config_path)

    # --- About tab ---
    about_frame = ttk.Frame(notebook)
    notebook.add(about_frame, text="About")
    about.build_about_tab(about_frame)

    # Select initial tab if requested.
    if initial_tab is not None:
        for tab_id in notebook.tabs():
            if notebook.tab(tab_id, "text") == initial_tab:
                notebook.select(tab_id)
                break

    # --- Bottom bar ---
    bottom_frame = ttk.Frame(win)
    bottom_frame.pack(fill="x", padx=8, pady=(0, 8))

    def _quit() -> None:
        _on_close()
        if on_quit is not None:
            on_quit()
        else:
            root.quit()

    ttk.Button(bottom_frame, text="Close (background)", command=_on_close).pack(side="right", padx=(0, 4))
    ttk.Button(bottom_frame, text="Quit", command=_quit).pack(side="right")


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
    config: dict | None = None,
    config_path: Path | None = None,
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
        columns=("recording", "timestamp", "description", "category", "file_path", "timestamp_ms", "id"),
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
    # Button rows
    # ------------------------------------------------------------------ #
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill="x", padx=8, pady=(0, 2))

    set_cat_frame = ttk.Frame(parent)
    set_cat_frame.pack(fill="x", padx=8, pady=(0, 8))

    set_cat_var = tk.StringVar()

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

        # Rebuild set-category combobox values.
        set_cat_combo["values"] = categories

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
                    row["id"],
                ),
            )

    ttk.Button(filter_frame, text="Refresh", command=_refresh).pack(side="left")

    recording_combo.bind("<<ComboboxSelected>>", lambda _e: _refresh())
    category_combo.bind("<<ComboboxSelected>>", lambda _e: _refresh())

    def _select_all() -> None:
        tree.selection_set(tree.get_children())

    def _unselect_all() -> None:
        tree.selection_set([])

    def _delete_selected() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select at least one row before deleting.")
            return
        n = len(selected)
        if not messagebox.askyesno("Delete markers", f"Delete {n} marker(s)?"):
            return
        for item_id in selected:
            marker_id = int(tree.item(item_id, "values")[6])
            delete_marker(marker_id, db_path=db_path)
        _refresh()

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
                # values order: recording(basename), timestamp_hms, description, category, file_path, timestamp_ms, id
                _recording, timestamp_hms, description, category, file_path, timestamp_ms, _id = vals
                writer.writerow([file_path, timestamp_ms, timestamp_hms, description, category])

    def _export_edl() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select at least one row before exporting.")
            return

        live_config = config if config is not None else {}
        initial_fps = live_config.get("last_export_fps", 60)
        opts = _ask_edl_options(parent, initial_fps)
        if opts is None:
            return
        fps, start_tc = opts

        # Persist chosen fps.
        live_config["last_export_fps"] = fps
        save_config(live_config, config_path=config_path)

        # Re-query all markers to get begin_timestamp_ms via id.
        all_rows = query_markers(db_path=db_path)
        rows_by_id = {r["id"]: r for r in all_rows}

        # Collect selected rows and group by file_path, preserving tree order.
        groups: dict[str, list[dict]] = defaultdict(list)
        for item_id in selected:
            vals = tree.item(item_id, "values")
            # values order: recording, timestamp_hms, description, category, file_path, timestamp_ms, id
            marker_id = int(vals[6])
            if marker_id in rows_by_id:
                row = rows_by_id[marker_id]
                groups[row["file_path"]].append(row)

        if len(groups) == 1:
            (file_path, group_rows) = next(iter(groups.items()))
            stem = Path(file_path).stem
            out_path = filedialog.asksaveasfilename(
                defaultextension=".edl",
                filetypes=[("EDL files", "*.edl"), ("All files", "*.*")],
                initialfile=f"{stem}.edl",
                title="Export markers to DaVinci Resolve EDL",
            )
            if not out_path:
                return
            edl_text = resolve_export.markers_to_edl(group_rows, fps=fps, start_tc=start_tc, title=stem)
            with open(out_path, "w", newline="", encoding="utf-8") as fh:
                fh.write(edl_text)
        else:
            out_dir = filedialog.askdirectory(title="Select folder for EDL files")
            if not out_dir:
                return
            out_dir_path = Path(out_dir)
            written: list[str] = []
            for file_path, group_rows in groups.items():
                stem = Path(file_path).stem
                # Sanitize stem for use as a filename.
                safe_stem = "".join(c if c not in r'\/:*?"<>|' else "_" for c in stem)
                candidate = out_dir_path / f"{safe_stem}.edl"
                counter = 2
                while candidate.exists():
                    candidate = out_dir_path / f"{safe_stem} ({counter}).edl"
                    counter += 1
                edl_text = resolve_export.markers_to_edl(group_rows, fps=fps, start_tc=start_tc, title=stem)
                with open(candidate, "w", newline="", encoding="utf-8") as fh:
                    fh.write(edl_text)
                written.append(candidate.name)
            messagebox.showinfo(
                "EDL Export",
                f"Wrote {len(written)} file(s):\n" + "\n".join(written),
            )

    ttk.Button(btn_frame, text="Select All", command=_select_all).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Unselect All", command=_unselect_all).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Delete", command=_delete_selected).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Export to CSV", command=_export_csv).pack(side="left", padx=(0, 4))
    ttk.Button(btn_frame, text="Export to DaVinci Resolve (.edl)", command=_export_edl).pack(side="left")
    tree.bind("<Delete>", lambda _e: _delete_selected())

    # Set category row
    set_cat_combo = ttk.Combobox(set_cat_frame, textvariable=set_cat_var, state="normal", width=18)

    def _set_category() -> None:
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select at least one row before setting a category.")
            return
        cat = set_cat_var.get().strip()
        if not cat:
            messagebox.showwarning("No category", "Enter or select a category first.")
            return
        ids = [int(tree.item(item_id, "values")[6]) for item_id in selected]
        update_markers_category(ids, cat, db_path=db_path)
        _refresh()

    ttk.Label(set_cat_frame, text="Set category:").pack(side="left", padx=(0, 4))
    set_cat_combo.pack(side="left", padx=(0, 4))
    ttk.Button(set_cat_frame, text="Set for Selection", command=_set_category).pack(side="left")

    # Register for new-marker notifications and populate on open.
    global _refresh_fn
    _refresh_fn = _refresh
    _refresh()
