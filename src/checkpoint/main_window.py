"""Main application window with Markers, Settings, and About tabs."""
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Any, Callable

from checkpoint.categories import load_categories, save_categories
from checkpoint.config import save_config
from checkpoint import about
from checkpoint.clip_explorer import ClipsTab
from checkpoint.resources import set_window_icon

# Module-level reference to the single open window instance (None when closed).
_window: tk.Toplevel | None = None

# Reference to the embedded ClipsTab; set when opened, cleared on close.
_clips_tab: ClipsTab | None = None


def notify_new_marker() -> None:
    """Refresh the Markers tab if the main window is currently open."""
    if _clips_tab is not None and _clips_tab.winfo_exists():
        _clips_tab.load_markers()


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
        global _window, _clips_tab
        if _clips_tab is not None:
            try:
                _clips_tab.teardown()
            except Exception:
                pass
            _clips_tab = None
        _window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # --- Markers tab (first) ---
    global _clips_tab
    _clips_tab = ClipsTab(notebook, db_path=db_path, config=config, config_path=config_path)
    notebook.add(_clips_tab, text="Markers")

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
