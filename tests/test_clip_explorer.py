"""Tests for clip_explorer.py — ClipsTab embedded Frame."""
import csv
import os
import tkinter as tk
import pytest
from unittest.mock import patch


@pytest.fixture()
def tk_root(_tk_session_root):
    """Per-test: yields shared session root, destroys ClipsTab children after each test."""
    yield _tk_session_root
    # Clean up any frames that were added as children.
    for child in list(_tk_session_root.winfo_children()):
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


def _make_tab(tk_root, db_path, config=None, config_path=None):
    """Create a ClipsTab and call update() so it's fully realized."""
    from checkpoint.clip_explorer import ClipsTab
    tab = ClipsTab(tk_root, db_path=db_path, config=config, config_path=config_path)
    tk_root.update()
    return tab


# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------

def test_module_importable():
    import checkpoint.clip_explorer  # noqa: F401


def test_clips_tab_class_exists():
    from checkpoint.clip_explorer import ClipsTab
    assert ClipsTab is not None


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_clips_tab_instantiates(tk_root, db_path):
    tab = _make_tab(tk_root, db_path)
    assert tab.winfo_exists()
    tab.teardown()


# ---------------------------------------------------------------------------
# Marker list populates from storage
# ---------------------------------------------------------------------------

def test_marker_list_populates(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another", "bug")

    tab = _make_tab(tk_root, db_path)
    assert len(tab._tree.get_children()) == 2
    tab.teardown()


# ---------------------------------------------------------------------------
# Keyword filter
# ---------------------------------------------------------------------------

def test_keyword_filter_narrows_list(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._keyword_var.set("great")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


def test_keyword_filter_empty_shows_all(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._keyword_var.set("")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 2
    tab.teardown()


# ---------------------------------------------------------------------------
# Recording filter
# ---------------------------------------------------------------------------

def test_recording_filter_narrows_list(tk_root, db_path):
    _insert_marker(db_path, "C:/recA.mkv", 30_000, 0, "A clip", "gameplay")
    _insert_marker(db_path, "C:/recB.mkv", 60_000, 30_000, "B clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._recording_var.set("C:/recA.mkv")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 1
    assert tab._tree.item(tab._tree.get_children()[0], "values")[4] == "A clip"
    tab.teardown()


def test_recording_filter_all_shows_all(tk_root, db_path):
    _insert_marker(db_path, "C:/recA.mkv", 30_000, 0, "A clip", "gameplay")
    _insert_marker(db_path, "C:/recB.mkv", 60_000, 30_000, "B clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._recording_var.set("All")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 2
    tab.teardown()


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------

def test_category_filter_narrows_list(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._category_var.set("gameplay")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


def test_category_all_shows_all(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "another clip", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._category_var.set("All")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 2
    tab.teardown()


# ---------------------------------------------------------------------------
# Duration filter
# ---------------------------------------------------------------------------

def test_min_duration_filter(tk_root, db_path):
    # duration = end - begin
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")        # 10s
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")         # 60s

    tab = _make_tab(tk_root, db_path)
    tab._min_dur_var.set("30")  # 30 seconds minimum
    tab._apply_filters()
    tk_root.update()
    # Only the 60s clip passes
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


def test_max_duration_filter(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")        # 10s
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")         # 60s

    tab = _make_tab(tk_root, db_path)
    tab._max_dur_var.set("20")  # 20 seconds maximum
    tab._apply_filters()
    tk_root.update()
    # Only the 10s clip passes
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


def test_min_max_duration_combined(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "10s", "")
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "30s", "")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "60s", "")

    tab = _make_tab(tk_root, db_path)
    tab._min_dur_var.set("15")
    tab._max_dur_var.set("45")
    tab._apply_filters()
    tk_root.update()
    # Only the 30s clip passes
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


def test_blank_duration_no_limit(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")

    tab = _make_tab(tk_root, db_path)
    tab._min_dur_var.set("")
    tab._max_dur_var.set("")
    tab._apply_filters()
    tk_root.update()
    assert len(tab._tree.get_children()) == 2
    tab.teardown()


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------

def test_keyword_and_category_combined(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 30_000, "great bug", "bug")
    _insert_marker(db_path, "C:/rec.mkv", 90_000, 60_000, "another gameplay", "gameplay")

    tab = _make_tab(tk_root, db_path)
    tab._keyword_var.set("great")
    tab._category_var.set("gameplay")
    tab._apply_filters()
    tk_root.update()
    # Only "great moment" in gameplay passes
    assert len(tab._tree.get_children()) == 1
    tab.teardown()


# ---------------------------------------------------------------------------
# Sort options
# ---------------------------------------------------------------------------

def test_sort_by_duration_asc(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")

    from checkpoint.clip_explorer import SORT_DURATION_ASC
    tab = _make_tab(tk_root, db_path)
    tab._sort_var.set(SORT_DURATION_ASC)
    tab._apply_filters()
    tk_root.update()

    rows = tab._tree.get_children()
    assert len(rows) == 2
    first_desc = tab._tree.item(rows[0], "values")[4]  # Description column
    assert first_desc == "short"
    tab.teardown()


def test_sort_by_duration_desc(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "long", "")
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "short", "")

    from checkpoint.clip_explorer import SORT_DURATION_DESC
    tab = _make_tab(tk_root, db_path)
    tab._sort_var.set(SORT_DURATION_DESC)
    tab._apply_filters()
    tk_root.update()

    rows = tab._tree.get_children()
    assert len(rows) == 2
    first_desc = tab._tree.item(rows[0], "values")[4]
    assert first_desc == "long"
    tab.teardown()


def test_sort_by_category(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "z-marker", "zebra")
    _insert_marker(db_path, "C:/rec.mkv", 60_000, 0, "a-marker", "alpha")

    from checkpoint.clip_explorer import SORT_CATEGORY
    tab = _make_tab(tk_root, db_path)
    tab._sort_var.set(SORT_CATEGORY)
    tab._apply_filters()
    tk_root.update()

    rows = tab._tree.get_children()
    assert len(rows) == 2
    first_cat = tab._tree.item(rows[0], "values")[5]  # Category column
    assert first_cat == "alpha"
    tab.teardown()


# ---------------------------------------------------------------------------
# Right pane: selecting a marker populates details
# ---------------------------------------------------------------------------

def test_selecting_marker_populates_right_pane(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "great moment", "gameplay")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    assert "great moment" in tab._desc_label.cget("text")
    assert "gameplay" in tab._cat_label.cget("text")
    tab.teardown()


# ---------------------------------------------------------------------------
# Active boundary: clicking Begin/End toggles highlight
# ---------------------------------------------------------------------------

def test_clicking_begin_activates_begin(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    tab._set_active_boundary("begin")
    tk_root.update()
    assert tab._active_boundary == "begin"
    tab.teardown()


def test_clicking_end_activates_end(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    tab._set_active_boundary("end")
    tk_root.update()
    assert tab._active_boundary == "end"
    tab.teardown()


def test_active_boundary_visual_distinction(tk_root, db_path):
    """The active boundary label gets a distinct foreground from the inactive one."""
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    tab._set_active_boundary("begin")
    tk_root.update()
    begin_fg = tab._begin_entry.cget("foreground")
    end_fg = tab._end_entry.cget("foreground")
    assert begin_fg != end_fg
    tab.teardown()


# ---------------------------------------------------------------------------
# Arrow key adjustments
# ---------------------------------------------------------------------------

def test_arrow_right_increases_active_boundary(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    old_end = tab._end_ms
    tab._adjust_boundary(5_000)
    tk_root.update()
    assert tab._end_ms == old_end + 5_000
    tab.teardown()


def test_arrow_left_decreases_active_boundary(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("begin")
    tk_root.update()

    old_begin = tab._begin_ms
    tab._adjust_boundary(-5_000)
    tk_root.update()
    # begin can't go below 0, so expect max(0, old_begin - 5000)
    assert tab._begin_ms == max(0, old_begin - 5_000)
    tab.teardown()


def test_arrow_keys_no_op_with_no_selection(tk_root, db_path):
    tab = _make_tab(tk_root, db_path)

    # No marker selected; _selected_marker_id should be None
    assert tab._selected_marker_id is None

    # Should not raise, should be no-op
    tab._adjust_boundary(5_000)
    tk_root.update()
    tab.teardown()


def test_arrow_key_event_default_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    old_end = tab._end_ms

    class FakeEvent:
        state = 0  # no modifier

    tab._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert tab._end_ms == old_end + 5_000
    tab.teardown()


def test_arrow_key_ctrl_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    old_end = tab._end_ms

    class FakeEvent:
        state = 4  # Ctrl modifier bit

    tab._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert tab._end_ms == old_end + 1_000
    tab.teardown()


def test_arrow_key_shift_step(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    old_end = tab._end_ms

    class FakeEvent:
        state = 1  # Shift modifier bit

    tab._on_arrow_key(FakeEvent(), +1)
    tk_root.update()
    assert tab._end_ms == old_end + 10_000
    tab.teardown()


# ---------------------------------------------------------------------------
# Persistence: adjustment persists to DB
# ---------------------------------------------------------------------------

def test_boundary_adjustment_persists_to_db(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    tab._adjust_boundary(5_000)
    tk_root.update()

    from checkpoint.storage import query_markers
    markers = query_markers(db_path=db_path)
    assert len(markers) == 1
    assert markers[0]["timestamp_ms"] == 35_000  # 30000 + 5000
    tab.teardown()


def test_begin_adjustment_persists_to_db(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 10_000, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("begin")
    tk_root.update()

    tab._adjust_boundary(5_000)
    tk_root.update()

    from checkpoint.storage import query_markers
    markers = query_markers(db_path=db_path)
    assert markers[0]["begin_timestamp_ms"] == 15_000  # 10000 + 5000
    tab.teardown()


# ---------------------------------------------------------------------------
# "Saved" label flashes after save
# ---------------------------------------------------------------------------

def test_saved_label_shows_after_adjustment(tk_root, db_path):
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    tab._adjust_boundary(5_000)
    tk_root.update()

    assert tab._saved_label.cget("text") == "Saved"
    tab.teardown()


# ---------------------------------------------------------------------------
# load_markers refreshes list
# ---------------------------------------------------------------------------

def test_load_markers_refreshes_list(tk_root, db_path):
    tab = _make_tab(tk_root, db_path)
    assert len(tab._tree.get_children()) == 0

    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "new clip", "gameplay")
    tab.load_markers()
    tk_root.update()

    assert len(tab._tree.get_children()) == 1
    tab.teardown()


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
        tab = _make_tab(tk_root, db_path)

        labels = [w for w in tab._video_frame.winfo_children() if isinstance(w, tk.Label)]
        texts = [lbl.cget("text") for lbl in labels]
        assert any("VLC" in t for t in texts), f"Expected VLC hint label, got: {texts}"
        tab.teardown()
    finally:
        ce.VLC_AVAILABLE = original


def test_vlc_absent_no_crash_on_marker_select(tk_root, db_path):
    """Selecting a marker when VLC is absent must not crash."""
    import checkpoint.clip_explorer as ce

    original = ce.VLC_AVAILABLE
    try:
        ce.VLC_AVAILABLE = False
        _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "clip", "")
        tab = _make_tab(tk_root, db_path)

        rows = tab._tree.get_children()
        tab._tree.selection_set(rows[0])
        tab._tree.focus(rows[0])
        tab._on_marker_select(None)
        tk_root.update()  # must not raise
        tab.teardown()
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
    """Player's set_hwnd is called during tab init."""
    tab = _make_tab(tk_root, db_path)
    assert mock_vlc.hwnd is not None
    tab.teardown()


def test_selecting_marker_with_existing_file_plays(tk_root, db_path, mock_vlc, tmp_path):
    """Selecting a marker whose file_path exists calls player.play()."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    assert mock_vlc.play_calls >= 1
    tab.teardown()


def test_seek_after_play_seeks_to_begin(tk_root, db_path, mock_vlc, tmp_path):
    """_seek_after_play() sets the player time to begin_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    # Directly invoke _seek_after_play to test the seek logic
    tab._seek_after_play()
    tk_root.update()

    assert 5_000 in mock_vlc.set_time_calls
    tab.teardown()


def test_file_not_found_shows_error_label(tk_root, db_path, mock_vlc):
    """Selecting a marker with missing file_path shows error label, no crash."""
    _insert_marker(db_path, "C:/nonexistent/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    labels = [w for w in tab._video_frame.winfo_children() if isinstance(w, tk.Label)]
    texts = [lbl.cget("text") for lbl in labels]
    assert any(t for t in texts), f"Expected error label in video frame, got: {texts}"
    assert mock_vlc.play_calls == 0
    tab.teardown()


def test_file_not_found_logs_warning(tk_root, db_path, mock_vlc, caplog):
    """Selecting a marker with missing file_path logs a warning."""
    import logging
    _insert_marker(db_path, "C:/nonexistent/rec.mkv", 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])

    with caplog.at_level(logging.WARNING, logger="checkpoint.clip_explorer"):
        tab._on_marker_select(None)
        tk_root.update()

    assert any("nonexistent" in r.message or "rec.mkv" in r.message for r in caplog.records), \
        f"Expected warning log, got: {caplog.records}"
    tab.teardown()


def test_check_loop_seeks_to_begin_when_past_end(tk_root, db_path, mock_vlc, tmp_path):
    """_check_loop resets player to begin_ms when get_time() >= end_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    # Simulate player past end
    mock_vlc._playing = True
    mock_vlc._time_ms = 31_000  # past end_ms=30_000
    mock_vlc.set_time_calls.clear()

    tab._check_loop()
    tk_root.update()

    assert tab._begin_ms in mock_vlc.set_time_calls
    tab.teardown()


def test_check_loop_no_seek_before_end(tk_root, db_path, mock_vlc, tmp_path):
    """_check_loop does not seek when player time is before end_ms."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    mock_vlc._playing = True
    mock_vlc._time_ms = 10_000  # before end_ms=30_000
    mock_vlc.set_time_calls.clear()

    tab._check_loop()
    tk_root.update()

    assert len(mock_vlc.set_time_calls) == 0
    tab.teardown()


def test_play_pause_button_label_toggles(tk_root, db_path, mock_vlc, tmp_path):
    """Play/Pause button label toggles between 'Play' and 'Pause'."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 0, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    # Player is playing after selection; button should show "Pause"
    mock_vlc._playing = True
    tab._on_play()
    tk_root.update()
    label_after_pause = tab._play_btn.cget("text")

    # Player is now paused; button should show "Play"
    tab._on_play()
    tk_root.update()
    label_after_resume = tab._play_btn.cget("text")

    assert label_after_pause != label_after_resume
    tab.teardown()


def test_arrow_key_updates_loop_bounds(tk_root, db_path, mock_vlc, tmp_path):
    """Adjusting boundaries via arrow keys updates _begin_ms/_end_ms used by loop."""
    video_file = tmp_path / "rec.mkv"
    video_file.write_bytes(b"fake")

    _insert_marker(db_path, str(video_file), 30_000, 5_000, "clip", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tab._set_active_boundary("end")
    tk_root.update()

    old_end = tab._end_ms
    tab._adjust_boundary(5_000)
    tk_root.update()

    # _end_ms should be updated (loop uses this live)
    assert tab._end_ms == old_end + 5_000

    # Verify loop uses updated end_ms
    mock_vlc._playing = True
    mock_vlc._time_ms = old_end + 1_000  # past old end but before new end
    mock_vlc.set_time_calls.clear()
    tab._check_loop()
    tk_root.update()
    # Should NOT seek because we're before the new end
    assert len(mock_vlc.set_time_calls) == 0
    tab.teardown()


# ---------------------------------------------------------------------------
# Delete key in ClipsTab
# ---------------------------------------------------------------------------

def test_delete_key_deletes_selected_marker(tk_root, db_path):
    """<Delete> key with a selected marker calls _delete_selected and removes it from DB."""
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "to delete", "gameplay")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    assert tab._selected_marker_id is not None
    with patch("tkinter.messagebox.askyesno", return_value=True):
        tab._on_delete_key()
    tk_root.update()

    from checkpoint.storage import query_markers
    assert len(query_markers(db_path=db_path)) == 0
    tab.teardown()


def test_delete_key_no_op_with_no_selection(tk_root, db_path):
    """<Delete> key with no marker selected is a no-op."""
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "stay", "")

    tab = _make_tab(tk_root, db_path)
    # No rows selected — _delete_selected shows warning but we patch it
    with patch("tkinter.messagebox.showwarning"):
        tab._on_delete_key()
    tk_root.update()

    from checkpoint.storage import query_markers
    assert len(query_markers(db_path=db_path)) == 1
    tab.teardown()


def test_delete_key_no_op_with_entry_focus(tk_root, db_path):
    """<Delete> key is a no-op when an Entry widget has focus."""
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "stay", "")

    tab = _make_tab(tk_root, db_path)
    rows = tab._tree.get_children()
    tab._tree.selection_set(rows[0])
    tab._tree.focus(rows[0])
    tab._on_marker_select(None)
    tk_root.update()

    # Monkeypatch focus_get to return an Entry, simulating Entry focus.
    tab.focus_get = lambda: tab._begin_entry
    tab._on_delete_key()
    tk_root.update()

    from checkpoint.storage import query_markers
    assert len(query_markers(db_path=db_path)) == 1
    tab.teardown()


# ---------------------------------------------------------------------------
# Batch actions: select all / unselect all
# ---------------------------------------------------------------------------

def test_select_all(tk_root, db_path):
    """'Select All' selects every visible row."""
    _insert_marker(db_path, "C:/rec.mkv", 1_000, 0, "A", "x")
    _insert_marker(db_path, "C:/rec.mkv", 2_000, 0, "B", "x")
    _insert_marker(db_path, "C:/rec.mkv", 3_000, 0, "C", "x")

    tab = _make_tab(tk_root, db_path)
    tab._select_all()
    assert len(tab._tree.selection()) == 3
    tab.teardown()


def test_unselect_all(tk_root, db_path):
    """'Unselect All' clears the selection."""
    _insert_marker(db_path, "C:/rec.mkv", 1_000, 0, "A", "x")
    _insert_marker(db_path, "C:/rec.mkv", 2_000, 0, "B", "x")

    tab = _make_tab(tk_root, db_path)
    tab._select_all()
    assert len(tab._tree.selection()) == 2
    tab._unselect_all()
    assert len(tab._tree.selection()) == 0
    tab.teardown()


# ---------------------------------------------------------------------------
# Batch actions: export to CSV
# ---------------------------------------------------------------------------

def test_export_csv_with_selection(tk_root, db_path, tmp_path):
    """'Export to CSV' writes selected rows in the correct schema."""
    _insert_marker(db_path, r"C:\rec\video1.mkv", 5_000, 0, "My clip", "gameplay")

    tab = _make_tab(tk_root, db_path)
    tab._select_all()

    out_file = str(tmp_path / "export.csv")
    with patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        tab._export_csv()

    assert (tmp_path / "export.csv").exists()
    with open(out_file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["file_path"] == r"C:\rec\video1.mkv"
    assert row["timestamp_ms"] == "5000"
    assert row["description"] == "My clip"
    assert row["category"] == "gameplay"
    tab.teardown()


def test_export_csv_empty_selection_shows_warning(tk_root, db_path):
    """'Export to CSV' with no rows selected shows a warning."""
    tab = _make_tab(tk_root, db_path)

    with patch("tkinter.messagebox.showwarning") as mock_warn, \
         patch("tkinter.filedialog.asksaveasfilename") as mock_dialog:
        tab._export_csv()
        mock_warn.assert_called_once()
        mock_dialog.assert_not_called()
    tab.teardown()


# ---------------------------------------------------------------------------
# Batch actions: export to DaVinci Resolve (.edl)
# ---------------------------------------------------------------------------

def test_export_edl_no_selection_shows_warning(tk_root, db_path):
    """EDL export with no selection shows warning."""
    tab = _make_tab(tk_root, db_path)

    with patch("tkinter.messagebox.showwarning") as mock_warn, \
         patch("tkinter.filedialog.asksaveasfilename") as mock_save, \
         patch("checkpoint.clip_explorer._ask_edl_options") as mock_ask:
        tab._export_edl()
        mock_warn.assert_called_once()
        mock_save.assert_not_called()
        mock_ask.assert_not_called()
    tab.teardown()


def test_export_edl_single_recording_writes_file(tk_root, db_path, tmp_path):
    """Single-recording selection writes one .edl."""
    from checkpoint.resolve_export import markers_to_edl
    from checkpoint.storage import query_markers

    _insert_marker(db_path, r"C:\rec\video1.mkv", 30_000, 10_000, "Clip A", "gameplay")
    _insert_marker(db_path, r"C:\rec\video1.mkv", 60_000, 30_000, "Clip B", "bug")

    tab = _make_tab(tk_root, db_path)
    tab._select_all()

    out_file = str(tmp_path / "video1.edl")
    with patch("checkpoint.clip_explorer._ask_edl_options", return_value=(60, "01:00:00:00")), \
         patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        tab._export_edl()

    assert (tmp_path / "video1.edl").exists()

    # Build expected in the same order as the tree (SORT_CREATED_DESC: id descending).
    all_rows = query_markers(db_path=db_path)
    group = sorted(
        [r for r in all_rows if r["file_path"] == r"C:\rec\video1.mkv"],
        key=lambda r: r["id"], reverse=True,
    )
    expected = markers_to_edl(group, fps=60, start_tc="01:00:00:00", title="video1")

    with open(out_file, "r", newline="", encoding="utf-8") as fh:
        actual = fh.read()
    assert actual == expected
    tab.teardown()


def test_export_edl_two_recordings_writes_two_files(tk_root, db_path, tmp_path):
    """Multi-recording selection writes one .edl per recording."""
    _insert_marker(db_path, r"C:\rec\video1.mkv", 30_000, 10_000, "Clip A", "gameplay")
    _insert_marker(db_path, r"C:\rec\video2.mkv", 20_000, 5_000, "Clip B", "bug")

    tab = _make_tab(tk_root, db_path)
    out_dir = str(tmp_path / "edl_out")
    os.makedirs(out_dir, exist_ok=True)

    tab._select_all()

    with patch("checkpoint.clip_explorer._ask_edl_options", return_value=(60, "01:00:00:00")), \
         patch("tkinter.filedialog.askdirectory", return_value=out_dir), \
         patch("tkinter.messagebox.showinfo") as mock_info:
        tab._export_edl()
        mock_info.assert_called_once()

    assert (tmp_path / "edl_out" / "video1.edl").exists()
    assert (tmp_path / "edl_out" / "video2.edl").exists()
    tab.teardown()


def test_export_edl_persists_fps_to_config(tk_root, db_path, tmp_path):
    """The chosen fps is written to config after EDL export."""
    import json
    config_path = tmp_path / "config.json"
    config = {}

    _insert_marker(db_path, r"C:\rec\video1.mkv", 30_000, 10_000, "Clip", "x")

    tab = _make_tab(tk_root, db_path, config=config, config_path=config_path)
    tab._select_all()

    out_file = str(tmp_path / "video1.edl")
    with patch("checkpoint.clip_explorer._ask_edl_options", return_value=(30, "01:00:00:00")), \
         patch("tkinter.filedialog.asksaveasfilename", return_value=out_file):
        tab._export_edl()

    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved.get("last_export_fps") == 30
    tab.teardown()


# ---------------------------------------------------------------------------
# Batch actions: delete
# ---------------------------------------------------------------------------

def test_delete_no_selection_shows_warning(tk_root, db_path):
    """'Delete' with no selection shows a warning."""
    _insert_marker(db_path, r"C:\rec\v.mkv", 1_000, 0, "A", "x")

    tab = _make_tab(tk_root, db_path)

    with patch("tkinter.messagebox.showwarning") as mock_warn, \
         patch("tkinter.messagebox.askyesno") as mock_ask:
        tab._delete_selected()
        mock_warn.assert_called_once()
        mock_ask.assert_not_called()

    from checkpoint.storage import query_markers
    assert len(query_markers(db_path=db_path)) == 1
    tab.teardown()


def test_delete_confirm_no_does_not_delete(tk_root, db_path):
    """'Delete' with selection but 'No' confirmation leaves DB unchanged."""
    _insert_marker(db_path, r"C:\rec\v.mkv", 1_000, 0, "A", "x")

    tab = _make_tab(tk_root, db_path)
    tab._tree.selection_set(tab._tree.get_children())

    with patch("tkinter.messagebox.askyesno", return_value=False):
        tab._delete_selected()

    from checkpoint.storage import query_markers
    assert len(query_markers(db_path=db_path)) == 1
    tab.teardown()


def test_delete_selected_removes_rows_from_db(tk_root, db_path):
    """Deleting a selection removes those rows from the DB."""
    # Tree is SORT_CREATED_DESC so newest (highest id) is first.
    # Insert "Keep" last so it gets the highest id and appears at index 0.
    _insert_marker(db_path, r"C:\rec\v.mkv", 1_000, 0, "Delete1", "x")
    _insert_marker(db_path, r"C:\rec\v.mkv", 2_000, 0, "Delete2", "x")
    _insert_marker(db_path, r"C:\rec\v.mkv", 3_000, 0, "Keep", "x")

    tab = _make_tab(tk_root, db_path)
    # Tree order (id desc): Keep(0), Delete2(1), Delete1(2)
    # Select the last two (Delete2, Delete1).
    all_items = tab._tree.get_children()
    tab._tree.selection_set(list(all_items[1:]))

    with patch("tkinter.messagebox.askyesno", return_value=True):
        tab._delete_selected()
    tk_root.update()

    from checkpoint.storage import query_markers
    remaining = query_markers(db_path=db_path)
    assert len(remaining) == 1
    assert remaining[0]["description"] == "Keep"
    tab.teardown()


def test_delete_selected_removes_from_tree(tk_root, db_path):
    """After deletion, removed rows are gone from the Treeview."""
    _insert_marker(db_path, r"C:\rec\v.mkv", 1_000, 0, "A", "x")
    _insert_marker(db_path, r"C:\rec\v.mkv", 2_000, 0, "B", "x")

    tab = _make_tab(tk_root, db_path)
    tab._tree.selection_set(tab._tree.get_children())

    with patch("tkinter.messagebox.askyesno", return_value=True):
        tab._delete_selected()
    tk_root.update()

    assert len(tab._tree.get_children()) == 0
    tab.teardown()


def test_delete_key_binding_registered_on_tree(tk_root, db_path):
    """The <Delete> key is bound on the tree."""
    tab = _make_tab(tk_root, db_path)
    assert tab._tree.bind("<Delete>"), "<Delete> binding not registered on tree"
    tab.teardown()


# ---------------------------------------------------------------------------
# Batch actions: set category
# ---------------------------------------------------------------------------

def test_set_category_button_updates_db(tk_root, db_path):
    """'Set for Selection' updates the category of selected markers in the DB."""
    from checkpoint.storage import query_markers

    # Tree is SORT_CREATED_DESC: "B" (id=2) at index 0, "A" (id=1) at index 1.
    _insert_marker(db_path, r"C:\rec\v.mkv", 1_000, 0, "A", "old")
    _insert_marker(db_path, r"C:\rec\v.mkv", 2_000, 0, "B", "old")

    tab = _make_tab(tk_root, db_path)
    # Select the second item (index 1) which is "A" (id=1, older).
    second_item = tab._tree.get_children()[1]
    tab._tree.selection_set([second_item])

    tab._set_cat_var.set("newcat")
    tab._set_category()
    tk_root.update()

    rows = query_markers(db_path=db_path)
    cats = {r["description"]: r["category"] for r in rows}
    assert cats["A"] == "newcat"
    assert cats["B"] == "old"
    tab.teardown()


def test_set_category_no_selection_shows_warning(tk_root, db_path):
    """'Set for Selection' with nothing selected shows a warning."""
    tab = _make_tab(tk_root, db_path)

    with patch("tkinter.messagebox.showwarning") as mock_warn:
        tab._set_category()
        mock_warn.assert_called_once()
    tab.teardown()


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------

def test_teardown_no_error_without_player(tk_root, db_path):
    """teardown() does not raise when no VLC player is active."""
    tab = _make_tab(tk_root, db_path)
    tab.teardown()  # must not raise


# ---------------------------------------------------------------------------
# Click-drag range selection
# ---------------------------------------------------------------------------

def test_drag_selects_contiguous_range(tk_root, db_path):
    """Press-and-drag selects the contiguous range from anchor to cursor row."""
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "A", "x")
    _insert_marker(db_path, "C:/rec.mkv", 20_000, 0, "B", "x")
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "C", "x")

    tab = _make_tab(tk_root, db_path)
    children = tab._tree.get_children()
    # Monkeypatch identify_row: treat y as a direct index into children.
    tab._tree.identify_row = lambda y: children[y] if 0 <= y < len(children) else ""

    class _Ev:
        def __init__(self, y):
            self.y = y

    # Press at row 0, drag to row 2 — should select rows 0, 1, 2.
    tab._on_b1_press(_Ev(0))
    tab._on_b1_motion(_Ev(2))
    assert set(tab._tree.selection()) == set(children[0:3])
    tab.teardown()


def test_drag_reverse_direction_selects_range(tk_root, db_path):
    """Drag from a lower row up to a higher row also selects the full range."""
    _insert_marker(db_path, "C:/rec.mkv", 10_000, 0, "A", "x")
    _insert_marker(db_path, "C:/rec.mkv", 20_000, 0, "B", "x")
    _insert_marker(db_path, "C:/rec.mkv", 30_000, 0, "C", "x")

    tab = _make_tab(tk_root, db_path)
    children = tab._tree.get_children()
    tab._tree.identify_row = lambda y: children[y] if 0 <= y < len(children) else ""

    class _Ev:
        def __init__(self, y):
            self.y = y

    # Press at row 2, drag to row 0 — should still select rows 0, 1, 2.
    tab._on_b1_press(_Ev(2))
    tab._on_b1_motion(_Ev(0))
    assert set(tab._tree.selection()) == set(children[0:3])
    tab.teardown()


# ---------------------------------------------------------------------------
# Audio annotation label
# ---------------------------------------------------------------------------

def test_audio_annotation_label_present(tk_root, db_path):
    """The audio annotation label exists with the exact specified text."""
    _EXPECTED = (
        "Preview plays one audio track only — "
        "your recording still contains all recorded tracks."
    )
    tab = _make_tab(tk_root, db_path)
    assert tab._audio_note.cget("text") == _EXPECTED
    tab.teardown()


def test_audio_annotation_label_foreground_gray(tk_root, db_path):
    """The audio annotation label has gray foreground."""
    tab = _make_tab(tk_root, db_path)
    assert str(tab._audio_note.cget("foreground")) == "gray"
    tab.teardown()
