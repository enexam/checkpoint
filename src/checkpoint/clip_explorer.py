"""Clip Explorer window: browse, filter, sort, and edit clip boundaries."""
import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from checkpoint import storage
from checkpoint.resources import set_window_icon

try:
    import vlc  # type: ignore
    VLC_AVAILABLE = True
except Exception:
    # ImportError if python-vlc is absent; OSError/other if the native libvlc
    # library cannot be found (e.g. CI runners without VLC installed).
    VLC_AVAILABLE = False

_logger = logging.getLogger(__name__)

# Sort option constants (used by tests and UI).
SORT_CREATED_DESC = "Created ↓"
SORT_DURATION_ASC = "Duration ↑"
SORT_DURATION_DESC = "Duration ↓"
SORT_CATEGORY = "Category"

_SORT_OPTIONS = [SORT_CREATED_DESC, SORT_DURATION_ASC, SORT_DURATION_DESC, SORT_CATEGORY]

# Colour used to highlight the active boundary label.
_ACTIVE_FG = "#0078d4"
_INACTIVE_FG = "black"


def _parse_hms(text: str) -> int | None:
    """Parse HH:MM:SS.mmm to milliseconds. Returns None if invalid."""
    try:
        parts = text.strip().split(":")
        if len(parts) != 3:
            return None
        h, m = int(parts[0]), int(parts[1])
        sec_parts = parts[2].split(".")
        s = int(sec_parts[0])
        ms = int(sec_parts[1].ljust(3, "0")[:3]) if len(sec_parts) > 1 else 0
        return (h * 3600 + m * 60 + s) * 1000 + ms
    except (ValueError, IndexError):
        return None


def _get_vlc_exe() -> str | None:
    import shutil
    if p := shutil.which("vlc"):
        return p
    for p in [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]:
        if Path(p).exists():
            return p
    return None


# Module-level singleton reference.
_window: "ClipExplorer | None" = None


def open_clip_explorer(root: tk.Tk, db_path: Path | None = None) -> None:
    """Open the Clip Explorer window, or raise it if already open."""
    global _window
    if _window is not None and _window.winfo_exists():
        _window.deiconify()
        _window.lift()
        _window.focus_force()
        return
    _window = ClipExplorer(root, db_path=db_path)


def notify_new_marker() -> None:
    """Refresh the marker list if the Clip Explorer is open."""
    if _window is not None and _window.winfo_exists():
        _window.load_markers()


class ClipExplorer(tk.Toplevel):
    """Clip Explorer window.

    Left pane: filter controls + marker Treeview.
    Right pane: detail labels, boundary controls, video placeholder, Play button,
                and a "Saved" flash label.
    """

    def __init__(self, root: tk.Tk, db_path: Path | None = None) -> None:
        super().__init__(root)
        self.title("Clip Explorer")
        self.resizable(True, True)
        set_window_icon(self)

        self._db_path = db_path
        self._selected_marker_id: int | None = None
        self._begin_ms: int = 0
        self._end_ms: int = 0
        self._active_boundary: str = "begin"  # "begin" or "end"
        self._saved_after_id: str | None = None
        self._loop_after_id: str | None = None
        self._player: Any = None
        self._seeking: bool = False
        self._selected_file_path: str = ""

        self._build_ui()
        self.load_markers()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Initialize VLC after the window is realized so winfo_id() returns a valid HWND.
        self.after(0, self._init_vlc)

        # Arrow key bindings.
        self.bind("<Left>", lambda e: self._on_arrow_key(e, -1))
        self.bind("<Right>", lambda e: self._on_arrow_key(e, +1))
        self.bind("<Control-Left>", lambda e: self._on_arrow_key(e, -1))
        self.bind("<Control-Right>", lambda e: self._on_arrow_key(e, +1))
        self.bind("<Shift-Left>", lambda e: self._on_arrow_key(e, -1))
        self.bind("<Shift-Right>", lambda e: self._on_arrow_key(e, +1))
        self.bind("<Delete>", self._on_delete_key)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6)
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, minsize=200)
        paned.add(right, minsize=300)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        filter_frame = ttk.LabelFrame(parent, text="Filters")
        filter_frame.pack(fill="x", padx=4, pady=4)

        # Keyword
        ttk.Label(filter_frame, text="Keyword:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self._keyword_var = tk.StringVar()
        kw_entry = ttk.Entry(filter_frame, textvariable=self._keyword_var)
        kw_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self._keyword_var.trace_add("write", lambda *_: self._apply_filters())

        # Category
        ttk.Label(filter_frame, text="Category:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self._category_var = tk.StringVar(value="All")
        self._category_menu = ttk.OptionMenu(filter_frame, self._category_var, "All")
        self._category_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self._category_var.trace_add("write", lambda *_: self._apply_filters())

        # Min duration
        ttk.Label(filter_frame, text="Min dur (s):").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self._min_dur_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self._min_dur_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self._min_dur_var.trace_add("write", lambda *_: self._apply_filters())

        # Max duration
        ttk.Label(filter_frame, text="Max dur (s):").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        self._max_dur_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self._max_dur_var, width=8).grid(row=3, column=1, sticky="w", padx=4, pady=2)
        self._max_dur_var.trace_add("write", lambda *_: self._apply_filters())

        # Sort
        ttk.Label(filter_frame, text="Sort:").grid(row=4, column=0, sticky="w", padx=4, pady=2)
        self._sort_var = tk.StringVar(value=SORT_CREATED_DESC)
        sort_menu = ttk.OptionMenu(filter_frame, self._sort_var, SORT_CREATED_DESC, *_SORT_OPTIONS)
        sort_menu.grid(row=4, column=1, sticky="ew", padx=4, pady=2)
        self._sort_var.trace_add("write", lambda *_: self._apply_filters())

        filter_frame.columnconfigure(1, weight=1)

        # Treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("file", "begin", "end", "duration", "description", "category", "_id", "_begin_ms", "_end_ms"),
            displaycolumns=("file", "begin", "end", "duration", "description", "category"),
            show="headings",
            selectmode="browse",
        )
        for col, heading, width in [
            ("file", "File", 120),
            ("begin", "Begin", 90),
            ("end", "End", 90),
            ("duration", "Duration", 80),
            ("description", "Description", 160),
            ("category", "Category", 80),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_marker_select)

    def _build_right(self, parent: ttk.Frame) -> None:
        detail_frame = ttk.LabelFrame(parent, text="Details")
        detail_frame.pack(fill="x", padx=4, pady=4)

        ttk.Label(detail_frame, text="Description:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self._desc_label = ttk.Label(detail_frame, text="")
        self._desc_label.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(detail_frame, text="Category:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self._cat_label = ttk.Label(detail_frame, text="")
        self._cat_label.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # Boundary controls
        boundary_frame = ttk.LabelFrame(parent, text="Boundaries")
        boundary_frame.pack(fill="x", padx=4, pady=(0, 4))

        tk.Label(boundary_frame, text="Begin:").pack(side="left", padx=(8, 2), pady=4)
        self._begin_var = tk.StringVar(value="--")
        self._begin_entry = tk.Entry(boundary_frame, textvariable=self._begin_var, width=13, fg=_ACTIVE_FG)
        self._begin_entry.pack(side="left", padx=(0, 8), pady=4)
        self._begin_entry.bind("<FocusIn>", lambda _e: self._set_active_boundary("begin"))
        self._begin_entry.bind("<Return>", lambda _e: self._on_boundary_entry_commit("begin"))
        self._begin_entry.bind("<FocusOut>", lambda _e: self._on_boundary_entry_commit("begin"))

        tk.Label(boundary_frame, text="End:").pack(side="left", padx=(8, 2), pady=4)
        self._end_var = tk.StringVar(value="--")
        self._end_entry = tk.Entry(boundary_frame, textvariable=self._end_var, width=13, fg=_INACTIVE_FG)
        self._end_entry.pack(side="left", padx=(0, 8), pady=4)
        self._end_entry.bind("<FocusIn>", lambda _e: self._set_active_boundary("end"))
        self._end_entry.bind("<Return>", lambda _e: self._on_boundary_entry_commit("end"))
        self._end_entry.bind("<FocusOut>", lambda _e: self._on_boundary_entry_commit("end"))

        # Video frame — fills available right-pane space
        video_frame = tk.Frame(parent, bg="#222222")
        video_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self._video_frame = video_frame

        # Seeker
        seeker_frame = ttk.Frame(parent)
        seeker_frame.pack(fill="x", padx=4, pady=(0, 2))
        self._seeker_var = tk.DoubleVar(value=0.0)
        self._seeker = ttk.Scale(seeker_frame, from_=0, to=1000, variable=self._seeker_var, orient="horizontal")
        self._seeker.pack(fill="x")
        self._seeker.bind("<ButtonPress-1>", lambda _e: self._on_seeker_press())
        self._seeker.bind("<ButtonRelease-1>", lambda _e: self._on_seeker_release())

        # Controls row
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill="x", padx=4, pady=(0, 4))

        self._play_btn = ttk.Button(ctrl_frame, text="Play", command=self._on_play)
        self._play_btn.pack(side="left", padx=(0, 4))

        self._open_vlc_btn = ttk.Button(ctrl_frame, text="Open in VLC", command=self._open_in_vlc)
        self._open_vlc_btn.pack(side="left", padx=(0, 4))

        self._delete_btn = ttk.Button(ctrl_frame, text="Delete", command=self._on_delete)
        self._delete_btn.pack(side="left", padx=(0, 4))

        self._saved_label = tk.Label(ctrl_frame, text="", foreground="green")
        self._saved_label.pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_markers(self) -> None:
        """Reload markers from storage and re-apply current filters."""
        self._all_markers = storage.query_markers(db_path=self._db_path)
        self._refresh_category_menu()
        self._apply_filters()

    def _refresh_category_menu(self) -> None:
        categories = sorted({m["category"] for m in self._all_markers if m["category"]})
        menu = self._category_menu["menu"]
        menu.delete(0, "end")
        current = self._category_var.get()
        options = ["All"] + categories
        for opt in options:
            menu.add_command(label=opt, command=lambda v=opt: self._category_var.set(v))
        if current not in options:
            self._category_var.set("All")

    def _apply_filters(self) -> None:
        """Filter and sort _all_markers then repopulate the treeview."""
        keyword = self._keyword_var.get().strip().lower()
        category = self._category_var.get()

        min_dur_s = self._parse_duration(self._min_dur_var.get())
        max_dur_s = self._parse_duration(self._max_dur_var.get())

        filtered = []
        for m in self._all_markers:
            if keyword and keyword not in m["description"].lower():
                continue
            if category != "All" and m["category"] != category:
                continue
            duration_s = (m["timestamp_ms"] - (m["begin_timestamp_ms"] or 0)) / 1000.0
            if min_dur_s is not None and duration_s < min_dur_s:
                continue
            if max_dur_s is not None and duration_s > max_dur_s:
                continue
            filtered.append(m)

        sort = self._sort_var.get()
        if sort == SORT_DURATION_ASC:
            filtered.sort(key=lambda m: m["timestamp_ms"] - (m["begin_timestamp_ms"] or 0))
        elif sort == SORT_DURATION_DESC:
            filtered.sort(key=lambda m: m["timestamp_ms"] - (m["begin_timestamp_ms"] or 0), reverse=True)
        elif sort == SORT_CATEGORY:
            filtered.sort(key=lambda m: m["category"])
        # SORT_CREATED_DESC: keep DB insertion order (id ascending = created descending by default)
        # We sort by id descending to show newest first.
        elif sort == SORT_CREATED_DESC:
            filtered.sort(key=lambda m: m["id"], reverse=True)

        self._tree.delete(*self._tree.get_children())
        for m in filtered:
            begin_ms = m["begin_timestamp_ms"] or 0
            end_ms = m["timestamp_ms"]
            duration_ms = end_ms - begin_ms
            self._tree.insert(
                "", "end",
                values=(
                    Path(m["file_path"]).name,
                    storage._ms_to_hms(begin_ms),
                    m["timestamp_hms"],
                    storage._ms_to_hms(duration_ms),
                    m["description"],
                    m["category"],
                    m["id"],
                    begin_ms,
                    end_ms,
                ),
            )

    @staticmethod
    def _parse_duration(text: str) -> float | None:
        """Parse a seconds string to float, or return None if blank/invalid."""
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Selection / right pane
    # ------------------------------------------------------------------

    def _on_marker_select(self, _event: Any) -> None:
        selected = self._tree.selection()
        if not selected:
            self._selected_marker_id = None
            return
        values = self._tree.item(selected[0], "values")
        # values: file, begin_hms, end_hms, duration_hms, description, category, _id, _begin_ms, _end_ms
        desc = values[4]
        cat = values[5]
        marker_id = int(values[6])
        begin_ms = int(values[7])
        end_ms = int(values[8])

        # Retrieve the full file path from storage (treeview only shows filename).
        markers = storage.query_markers(db_path=self._db_path)
        file_path: str = ""
        for m in markers:
            if m["id"] == marker_id:
                file_path = m["file_path"]
                break

        self._selected_marker_id = marker_id
        self._selected_file_path = file_path
        self._begin_ms = begin_ms
        self._end_ms = end_ms

        self._desc_label.configure(text=desc)
        self._cat_label.configure(text=cat)
        self._refresh_boundary_entries()

        if VLC_AVAILABLE and self._player is not None:
            self._load_media(file_path)

    def _refresh_boundary_entries(self) -> None:
        self._begin_var.set(storage._ms_to_hms(self._begin_ms))
        self._end_var.set(storage._ms_to_hms(self._end_ms))

    # ------------------------------------------------------------------
    # Active boundary
    # ------------------------------------------------------------------

    def _set_active_boundary(self, which: str) -> None:
        """Set which boundary ('begin' or 'end') is active and update visuals."""
        self._active_boundary = which
        if which == "begin":
            self._begin_entry.configure(fg=_ACTIVE_FG)
            self._end_entry.configure(fg=_INACTIVE_FG)
        else:
            self._begin_entry.configure(fg=_INACTIVE_FG)
            self._end_entry.configure(fg=_ACTIVE_FG)

    # ------------------------------------------------------------------
    # Arrow key handling
    # ------------------------------------------------------------------

    def _on_arrow_key(self, event: Any, direction: int) -> None:
        """Handle a directional arrow key event.

        direction: +1 for Right, -1 for Left.
        Modifier detection uses event.state bit flags:
          - Shift: bit 0 (state & 1)
          - Ctrl:  bit 2 (state & 4)
        """
        if isinstance(self.focus_get(), tk.Entry):
            return
        state = getattr(event, "state", 0)
        if state & 4:
            step = 1_000
        elif state & 1:
            step = 10_000
        else:
            step = 5_000
        self._adjust_boundary(direction * step)

    def _adjust_boundary(self, delta_ms: int) -> None:
        """Move the active boundary by delta_ms milliseconds, persist, and flash."""
        if self._selected_marker_id is None:
            return

        if self._active_boundary == "begin":
            new_begin = max(0, self._begin_ms + delta_ms)
            self._begin_ms = new_begin
        else:
            new_end = max(0, self._end_ms + delta_ms)
            self._end_ms = new_end

        storage.update_marker_boundaries(
            self._selected_marker_id,
            self._begin_ms,
            self._end_ms,
            db_path=self._db_path,
        )
        self._refresh_boundary_entries()
        self._flash_saved()

    def _flash_saved(self) -> None:
        """Show 'Saved' in green for 1 second."""
        self._saved_label.configure(text="Saved")
        if self._saved_after_id is not None:
            self.after_cancel(self._saved_after_id)
        self._saved_after_id = self.after(1_000, lambda: self._saved_label.configure(text=""))

    # ------------------------------------------------------------------
    # VLC player
    # ------------------------------------------------------------------

    def _init_vlc(self) -> None:
        """Create the VLC player (called after window is realized) or show fallback."""
        if VLC_AVAILABLE:
            try:
                self._vlc_instance = vlc.Instance()  # type: ignore[name-defined]
                self._player = self._vlc_instance.media_player_new()
                self._player.set_hwnd(self._video_frame.winfo_id())
                self._schedule_loop()
                return
            except Exception:
                _logger.warning("VLC native library not found; video preview disabled")
        tk.Label(
            self._video_frame,
            text="Install VLC to enable video preview",
            bg="#222222",
            fg="#888888",
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _clear_video_frame_labels(self) -> None:
        """Remove any Label widgets from the video frame (error/fallback labels)."""
        for child in list(self._video_frame.winfo_children()):
            if isinstance(child, tk.Label):
                child.destroy()

    def _load_media(self, file_path: str) -> None:
        """Load and play the media file, or show an error if it doesn't exist."""
        if not Path(file_path).exists():
            _logger.warning("Video file not found: %s", file_path)
            self._player.stop()
            self._clear_video_frame_labels()
            tk.Label(
                self._video_frame,
                text=f"File not found: {Path(file_path).name}",
                bg="#222222",
                fg="#cc4444",
            ).place(relx=0.5, rely=0.5, anchor="center")
            return

        self._seeker_var.set(0.0)
        self._clear_video_frame_labels()
        media = self._vlc_instance.media_new(file_path)
        self._player.set_media(media)
        self._player.play()
        self._play_btn.configure(text="Pause")
        self.after(300, self._seek_after_play)

    def _seek_after_play(self) -> None:
        """Seek to begin_ms after a short delay to let VLC start playback."""
        if self._player is not None:
            self._player.set_time(self._begin_ms)

    def _schedule_loop(self) -> None:
        """Schedule the next _check_loop tick."""
        if self.winfo_exists():
            self._loop_after_id = self.after(100, self._check_loop)

    def _check_loop(self) -> None:
        """Loop playback within [begin_ms, end_ms] and update the seeker."""
        if self._player is not None and self._player.is_playing():
            current = self._player.get_time()
            if current >= self._end_ms:
                self._player.set_time(self._begin_ms)
            elif not self._seeking:
                length = self._player.get_length()
                if length > 0:
                    self._seeker_var.set(current / length * 1000)
        self._schedule_loop()

    def _on_play(self) -> None:
        """Toggle play/pause and update button label."""
        if self._player is None:
            return
        if self._player.is_playing():
            self._player.pause()
            self._play_btn.configure(text="Play")
        else:
            self._player.play()
            self._play_btn.configure(text="Pause")

    def _on_boundary_entry_commit(self, which: str) -> None:
        if self._selected_marker_id is None:
            return
        var = self._begin_var if which == "begin" else self._end_var
        ms = _parse_hms(var.get())
        if ms is None:
            self._refresh_boundary_entries()
            return
        ms = max(0, ms)
        if which == "begin":
            self._begin_ms = ms
        else:
            self._end_ms = ms
        storage.update_marker_boundaries(
            self._selected_marker_id, self._begin_ms, self._end_ms, db_path=self._db_path
        )
        self._refresh_boundary_entries()
        self._flash_saved()

    def _on_delete(self) -> None:
        if self._selected_marker_id is None:
            return
        storage.delete_marker(self._selected_marker_id, db_path=self._db_path)
        self._selected_marker_id = None
        self._selected_file_path = ""
        self._begin_ms = 0
        self._end_ms = 0
        self._desc_label.configure(text="")
        self._cat_label.configure(text="")
        self._begin_var.set("--")
        self._end_var.set("--")
        if self._player is not None:
            self._player.stop()
            self._play_btn.configure(text="Play")
        self.load_markers()

    def _on_delete_key(self, _event: Any = None) -> None:
        """Handle the Delete key: no-op if an Entry has focus or no marker is selected."""
        if isinstance(self.focus_get(), tk.Entry):
            return
        if self._selected_marker_id is None:
            return
        self._on_delete()

    def _on_seeker_press(self) -> None:
        self._seeking = True

    def _on_seeker_release(self) -> None:
        if self._player is not None:
            length = self._player.get_length()
            if length > 0:
                self._player.set_time(int(self._seeker_var.get() / 1000 * length))
        self._seeking = False

    def _open_in_vlc(self) -> None:
        if not self._selected_file_path:
            _logger.warning("Open in VLC: no file selected")
            return
        exe = _get_vlc_exe()
        if exe is None:
            _logger.warning("Open in VLC: VLC executable not found")
            return
        import subprocess
        cmd = [exe, f"--start-time={self._begin_ms / 1000:.3f}", f"--stop-time={self._end_ms / 1000:.3f}", str(Path(self._selected_file_path))]
        _logger.info("Open in VLC: %s", cmd)
        try:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            _logger.exception("Open in VLC: Popen failed")

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        global _window
        if self._loop_after_id is not None:
            self.after_cancel(self._loop_after_id)
            self._loop_after_id = None
        if self._player is not None:
            self._player.stop()
        _window = None
        self.destroy()
