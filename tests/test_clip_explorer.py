"""Tests for clip_explorer.py (task 3: clip explorer window)."""
import tkinter as tk
import pytest


@pytest.fixture()
def tk_root(_tk_session_root):
    """Per-test: yields shared session root, destroys Toplevel children after each test."""
    yield _tk_session_root
    import checkpoint.clip_explorer as ce
    ce._window = None
    for child in list(_tk_session_root.winfo_children()):
        if isinstance(child, tk.Toplevel):
            try:
                child.destroy()
            except tk.TclError:
                pass


@pytest.fixture()
def db_path(tmp_path):
    """Temporary SQLite DB for each test."""
    return tmp_path / "markers.db"


def _insert_marker(db_path, file_path, timestamp_ms, begin_ms, description, category, duration_hint_ms=30_000):
    from checkpoint.storage import append_marker
    append_marker(file_path, timestamp_ms, description, category, begin_ms, duration_hint_ms, db_path=db_path)


# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------

def test_module_importable():
    import checkpoint.clip_explorer  # noqa: F401


def test_clip_explorer_class_exists():
    from checkpoint.clip_explorer import ClipExplorer
    assert ClipExplorer is not None


def test_open_clip_explorer_callable():
    from checkpoint.clip_explorer import open_clip_explorer
    assert callable(open_clip_explorer)


def test_notify_new_marker_callable():
    from checkpoint.clip_explorer import notify_new_marker
    assert callable(notify_new_marker)


# ---------------------------------------------------------------------------
# Window open / raise / singleton
# ---------------------------------------------------------------------------

def test_open_creates_toplevel(tk_root, db_path):
    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()
    children = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(children) == 1


def test_open_twice_raises_existing(tk_root, db_path):
    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()
    children = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(children) == 1


# ---------------------------------------------------------------------------
# Marker list populates from storage
# ---------------------------------------------------------------------------

def test_marker_list_populates(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another", "bug")

    from checkpoint.clip_explorer import open_clip_explorer, ClipExplorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    assert win is not None
    # Two rows in the treeview
    assert len(win._tree.get_children()) == 2


# ---------------------------------------------------------------------------
# Keyword filter
# ---------------------------------------------------------------------------

def test_keyword_filter_narrows_list(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._keyword_var.set("great")
    win._apply_filters()
    tk_root.update()
    assert len(win._tree.get_children()) == 1


def test_keyword_filter_empty_shows_all(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._keyword_var.set("")
    win._apply_filters()
    tk_root.update()
    assert len(win._tree.get_children()) == 2


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------

def test_category_filter_narrows_list(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._category_var.set("gameplay")
    win._apply_filters()
    tk_root.update()
    assert len(win._tree.get_children()) == 1


def test_category_all_shows_all(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._category_var.set("All")
    win._apply_filters()
    tk_root.update()
    assert len(win._tree.get_children()) == 2


# ---------------------------------------------------------------------------
# Duration filter
# ---------------------------------------------------------------------------

def test_min_duration_filter(tk_root, db_path):
    # duration = end - begin
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")        # 10s
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")         # 60s

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._min_dur_var.set("30")  # 30 seconds minimum
    win._apply_filters()
    tk_root.update()
    # Only the 60s clip passes
    assert len(win._tree.get_children()) == 1


def test_max_duration_filter(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")        # 10s
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")         # 60s

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._max_dur_var.set("20")  # 20 seconds maximum
    win._apply_filters()
    tk_root.update()
    # Only the 10s clip passes
    assert len(win._tree.get_children()) == 1


def test_min_max_duration_combined(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "10s", "")
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "30s", "")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "60s", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._min_dur_var.set("15")
    win._max_dur_var.set("45")
    win._apply_filters()
    tk_root.update()
    # Only the 30s clip passes
    assert len(win._tree.get_children()) == 1


def test_blank_duration_no_limit(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._min_dur_var.set("")
    win._max_dur_var.set("")
    win._apply_filters()
    tk_root.update()
    assert len(win._tree.get_children()) == 2


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------

def test_keyword_and_category_combined(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "great bug", "bug")
    _insert_marker(db_path, "C:/rec.mkv", 90_000, 60_000, "another gameplay", "gameplay")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._keyword_var.set("great")
    win._category_var.set("gameplay")
    win._apply_filters()
    tk_root.update()
    # Only "great moment" in gameplay passes
    assert len(win._tree.get_children()) == 1


# ---------------------------------------------------------------------------
# Sort options
# ---------------------------------------------------------------------------

def test_sort_by_duration_asc(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")

    from checkpoint.clip_explorer import open_clip_explorer, SORT_DURATION_ASC
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._sort_var.set(SORT_DURATION_ASC)
    win._apply_filters()
    tk_root.update()

    rows = win._tree.get_children()
    assert len(rows) == 2
    first_desc = win._tree.item(rows[0], "values")[4]  # Description column
    assert first_desc == "short"


def test_sort_by_duration_desc(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")

    from checkpoint.clip_explorer import open_clip_explorer, SORT_DURATION_DESC
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._sort_var.set(SORT_DURATION_DESC)
    win._apply_filters()
    tk_root.update()

    rows = win._tree.get_children()
    assert len(rows) == 2
    first_desc = win._tree.item(rows[0], "values")[4]
    assert first_desc == "long"


def test_sort_by_category(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "z-marker", "zebra")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "a-marker", "alpha")

    from checkpoint.clip_explorer import open_clip_explorer, SORT_CATEGORY
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    win._sort_var.set(SORT_CATEGORY)
    win._apply_filters()
    tk_root.update()

    rows = win._tree.get_children()
    assert len(rows) == 2
    first_cat = win._tree.item(rows[0], "values")[5]  # Category column
    assert first_cat == "alpha"


# ---------------------------------------------------------------------------
# Right pane: selecting a marker populates details
# ---------------------------------------------------------------------------

def test_selecting_marker_populates_right_pane(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    assert "great moment" in win._desc_label.cget("text")
    assert "gameplay" in win._cat_label.cget("text")


# ---------------------------------------------------------------------------
# Active boundary: clicking Begin/End toggles highlight
# ---------------------------------------------------------------------------

def test_clicking_begin_activates_begin(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    win._set_active_boundary("begin")
    tk_root.update()
    assert win._active_boundary == "begin"


def test_clicking_end_activates_end(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    win._set_active_boundary("end")
    tk_root.update()
    assert win._active_boundary == "end"


def test_active_boundary_visual_distinction(tk_root, db_path):
    """The active boundary label gets a distinct foreground from the inactive one."""
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    win._set_active_boundary("begin")
    tk_root.update()
    begin_fg = win._begin_entry.cget("foreground")
    end_fg = win._end_entry.cget("foreground")
    assert begin_fg != end_fg


# ---------------------------------------------------------------------------
# Arrow key adjustments
# ---------------------------------------------------------------------------

def test_arrow_right_increases_active_boundary(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    old_end = win._end_ms
    win._adjust_boundary(5_000)
    tk_root.update()
    assert win._end_ms == old_end + 5_000


def test_arrow_left_decreases_active_boundary(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("begin")
    tk_root.update()

    old_begin = win._begin_ms
    win._adjust_boundary(-5_000)
    tk_root.update()
    # begin can't go below 0, so expect max(0, old_begin - 5000)
    assert win._begin_ms == max(0, old_begin - 5_000)


def test_arrow_keys_no_op_with_no_selection(tk_root, db_path):
    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    # No marker selected; _selected_marker_id should be None
    assert win._selected_marker_id is None

    # Should not raise, should be no-op
    win._adjust_boundary(5_000)
    tk_root.update()


def test_arrow_key_event_default_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    old_end = win._end_ms

    class FakeEvent:
        state = 0  # no modifier

    win._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert win._end_ms == old_end + 5_000


def test_arrow_key_ctrl_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    old_end = win._end_ms

    class FakeEvent:
        state = 4  # Ctrl modifier bit

    win._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert win._end_ms == old_end + 1_000


def test_arrow_key_shift_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    old_end = win._end_ms

    class FakeEvent:
        state = 1  # Shift modifier bit

    win._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert win._end_ms == old_end + 10_000


# ---------------------------------------------------------------------------
# Persistence: adjustment persists to DB
# ---------------------------------------------------------------------------

def test_boundary_adjustment_persists_to_db(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    win._adjust_boundary(5_000)
    tk_root.update()

    from checkpoint.storage import query_markers
    markers = query_markers(db_path=db_path)
    assert len(markers) == 1
    assert markers[0]["timestamp_ms"] == 35_000  # 30000 + 5000


def test_begin_adjustment_persists_to_db(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 10_000, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("begin")
    tk_root.update()

    win._adjust_boundary(5_000)
    tk_root.update()

    from checkpoint.storage import query_markers
    markers = query_markers(db_path=db_path)
    assert markers[0]["begin_timestamp_ms"] == 15_000  # 10000 + 5000


# ---------------------------------------------------------------------------
# "Saved" label flashes after save
# ---------------------------------------------------------------------------

def test_saved_label_shows_after_adjustment(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window

    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    win._adjust_boundary(5_000)
    tk_root.update()

    assert win._saved_label.cget("text") == "Saved"


# ---------------------------------------------------------------------------
# notify_new_marker refreshes list when window is open
# ---------------------------------------------------------------------------

def test_notify_new_marker_refreshes_list(tk_root, db_path):
    from checkpoint.clip_explorer import open_clip_explorer, notify_new_marker
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    assert len(win._tree.get_children()) == 0

    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "new clip", "gameplay")
    notify_new_marker()
    tk_root.update()

    assert len(win._tree.get_children()) == 1


def test_notify_new_marker_no_op_when_closed(db_path):
    """notify_new_marker does not crash when no window is open."""
    import checkpoint.clip_explorer as ce
    ce._window = None
    from checkpoint.clip_explorer import notify_new_marker
    notify_new_marker()  # should not raise


# ---------------------------------------------------------------------------
# VLC: guard import — no ImportError when vlc is absent
# ---------------------------------------------------------------------------

def test_vlc_available_flag_exists():
    import checkpoint.clip_explorer as ce
    assert hasattr(ce, "VLC_AVAILABLE")


def test_no_import_error_when_vlc_missing():
    """Importing clip_explorer must never raise ImportError regardless of vlc."""
    import importlib
    import sys
    # Remove vlc from sys.modules if present, simulate absent vlc
    vlc_mod = sys.modules.pop("vlc", None)
    try:
        import checkpoint.clip_explorer  # noqa: F401 — must not raise
    finally:
        if vlc_mod is not None:
            sys.modules["vlc"] = vlc_mod


# ---------------------------------------------------------------------------
# VLC absent: fallback label in video frame
# ---------------------------------------------------------------------------

def test_vlc_absent_shows_fallback_label(tk_root, db_path):
    """When VLC_AVAILABLE is False, video frame contains a fallback Label."""
    import checkpoint.clip_explorer as ce

    original = ce.VLC_AVAILABLE
    try:
        ce.VLC_AVAILABLE = False
        from checkpoint.clip_explorer import open_clip_explorer
        open_clip_explorer(tk_root, db_path=db_path)
        tk_root.update()

        win = ce._window
        labels = [w for w in win._video_frame.winfo_children() if isinstance(w, tk.Label)]
        texts = [lbl.cget("text") for lbl in labels]
        assert any("VLC" in t for t in texts), f"Expected VLC hint label, got: {texts}"
    finally:
        ce.VLC_AVAILABLE = original


def test_vlc_absent_no_crash_on_marker_select(tk_root, db_path):
    """Selecting a marker when VLC is absent must not crash."""
    import checkpoint.clip_explorer as ce

    original = ce.VLC_AVAILABLE
    try:
        ce.VLC_AVAILABLE = False
        _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")
        from checkpoint.clip_explorer import open_clip_explorer
        open_clip_explorer(tk_root, db_path=db_path)
        tk_root.update()

        win = ce._window
        rows = win._tree.get_children()
        win._tree.selection_set(rows[0])
        win._on_marker_select(None)
        tk_root.update()  # must not raise
    finally:
        ce.VLC_AVAILABLE = original


# ---------------------------------------------------------------------------
# VLC present (mocked): marker selection loads media and plays
# ---------------------------------------------------------------------------

class _FakeMedia:
    pass


class _FakePlayer:
    def __init__(self):
        self.hwnd = None
        self.media = None
        self._playing = False
        self._time_ms = 0
        self.play_calls = 0
        self.pause_calls = 0
        self.set_time_calls = []

    def set_hwnd(self, hwnd):
        self.hwnd = hwnd

    def set_media(self, media):
        self.media = media

    def play(self):
        self._playing = True
        self.play_calls += 1

    def pause(self):
        self._playing = not self._playing
        self.pause_calls += 1

    def is_playing(self):
        return self._playing

    def get_time(self):
        return self._time_ms

    def get_length(self):
        return 60_000

    def set_time(self, ms):
        self._time_ms = ms
        self.set_time_calls.append(ms)

    def stop(self):
        self._playing = False


class _FakeInstance:
    def __init__(self, player):
        self._player = player

    def media_player_new(self):
        return self._player

    def media_new(self, path):
        m = _FakeMedia()
        m.path = path
        return m


@pytest.fixture()
def mock_vlc(tmp_path):
    """Monkeypatches clip_explorer to act as if VLC is available with a fake player."""
    import checkpoint.clip_explorer as ce

    player = _FakePlayer()
    instance = _FakeInstance(player)

    import types
    fake_vlc = types.ModuleType("vlc")
    fake_vlc.Instance = lambda: instance

    original_available = ce.VLC_AVAILABLE
    original_vlc = getattr(ce, "vlc", None)

    ce.VLC_AVAILABLE = True
    ce.vlc = fake_vlc

    yield player

    ce.VLC_AVAILABLE = original_available
    if original_vlc is None:
        if hasattr(ce, "vlc"):
            del ce.vlc
    else:
        ce.vlc = original_vlc


def test_vlc_player_set_hwnd_on_init(tk_root, db_path, mock_vlc):
    """Player's set_hwnd is called during window init."""
    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    assert mock_vlc.hwnd is not None


def test_selecting_marker_with_existing_file_plays(tk_root, db_path, mock_vlc, tmp_path):
    """Selecting a marker whose file_path exists calls player.play()."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    assert mock_vlc.play_calls >= 1


def test_seek_after_play_seeks_to_begin(tk_root, db_path, mock_vlc, tmp_path):
    """_seek_after_play() sets the player time to begin_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    # Directly invoke _seek_after_play to test the seek logic
    win._seek_after_play()
    tk_root.update()

    assert 5_000 in mock_vlc.set_time_calls


def test_file_not_found_shows_error_label(tk_root, db_path, mock_vlc):
    """Selecting a marker with missing file_path shows error label, no crash."""
    _insert_marker(db_path, "C:/nonexistent/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    labels = [w for w in win._video_frame.winfo_children() if isinstance(w, tk.Label)]
    texts = [lbl.cget("text") for lbl in labels]
    assert any(t for t in texts), f"Expected error label in video frame, got: {texts}"
    assert mock_vlc.play_calls == 0


def test_file_not_found_logs_warning(tk_root, db_path, mock_vlc, caplog):
    """Selecting a marker with missing file_path logs a warning."""
    import logging
    _insert_marker(db_path, "C:/nonexistent/rec.mkv", 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])

    with caplog.at_level(logging.WARNING, logger="checkpoint.clip_explorer"):
        win._on_marker_select(None)
        tk_root.update()

    assert any("nonexistent" in r.message or "rec.mkv" in r.message for r in caplog.records), \
        f"Expected warning log, got: {caplog.records}"


def test_check_loop_seeks_to_begin_when_past_end(tk_root, db_path, mock_vlc, tmp_path):
    """_check_loop resets player to begin_ms when get_time() >= end_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    # Simulate player past end
    mock_vlc._playing = True
    mock_vlc._time_ms = 31_000  # past end_ms=30_000
    mock_vlc.set_time_calls.clear()

    win._check_loop()
    tk_root.update()

    assert win._begin_ms in mock_vlc.set_time_calls


def test_check_loop_no_seek_before_end(tk_root, db_path, mock_vlc, tmp_path):
    """_check_loop does not seek when player time is before end_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    mock_vlc._playing = True
    mock_vlc._time_ms = 10_000  # before end_ms=30_000
    mock_vlc.set_time_calls.clear()

    win._check_loop()
    tk_root.update()

    assert len(mock_vlc.set_time_calls) == 0


def test_play_pause_button_label_toggles(tk_root, db_path, mock_vlc, tmp_path):
    """Play/Pause button label toggles between 'Play' and 'Pause'."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 0, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    tk_root.update()

    # Player is playing after selection; button should show "Pause"
    mock_vlc._playing = True
    win._on_play()
    tk_root.update()
    label_after_pause = win._play_btn.cget("text")

    # Player is now paused; button should show "Play"
    win._on_play()
    tk_root.update()
    label_after_resume = win._play_btn.cget("text")

    assert label_after_pause != label_after_resume


def test_arrow_key_updates_loop_bounds(tk_root, db_path, mock_vlc, tmp_path):
    """Adjusting boundaries via arrow keys updates _begin_ms/_end_ms used by loop."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    from checkpoint.clip_explorer import open_clip_explorer
    open_clip_explorer(tk_root, db_path=db_path)
    tk_root.update()

    import checkpoint.clip_explorer as ce
    win = ce._window
    rows = win._tree.get_children()
    win._tree.selection_set(rows[0])
    win._on_marker_select(None)
    win._set_active_boundary("end")
    tk_root.update()

    old_end = win._end_ms
    win._adjust_boundary(5_000)
    tk_root.update()

    # _end_ms should be updated (loop uses this live)
    assert win._end_ms == old_end + 5_000

    # Verify loop uses updated end_ms
    mock_vlc._playing = True
    mock_vlc._time_ms = old_end + 1_000  # past old end but before new end
    mock_vlc.set_time_calls.clear()
    win._check_loop()
    tk_root.update()
    # Should NOT seek because we're before the new end
    assert len(mock_vlc.set_time_calls) == 0
