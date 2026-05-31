"""Tests for resolve_export.py — DaVinci Resolve marker EDL generation."""

import sys

import pytest

from checkpoint.resolve_export import (
    _category_color,
    _frames_to_tc,
    _ms_to_frames,
    _sanitize_marker_name,
    _tc_to_frames,
    markers_to_edl,
)


# ---------------------------------------------------------------------------
# _ms_to_frames
# ---------------------------------------------------------------------------


def test_ms_to_frames_basic():
    assert _ms_to_frames(1000, 60) == 60


def test_ms_to_frames_marker1():
    """4816 ms at 60 fps = frame 289 (from the reference EDL)."""
    assert _ms_to_frames(4816, 60) == 289


def test_ms_to_frames_marker2():
    """606 ms at 60 fps = frame 606*60/1000 = 36.36 → 36."""
    # 606 * 60 / 1000 = 36.36 → round → 36
    assert _ms_to_frames(606, 60) == 36


def test_ms_to_frames_zero():
    assert _ms_to_frames(0, 30) == 0


# ---------------------------------------------------------------------------
# _frames_to_tc
# ---------------------------------------------------------------------------


def test_frames_to_tc_zero():
    assert _frames_to_tc(0, 60) == "00:00:00:00"


def test_frames_to_tc_one_second():
    assert _frames_to_tc(60, 60) == "00:00:01:00"


def test_frames_to_tc_rollover():
    """Frame 59 at 60 fps = last frame of second 0."""
    assert _frames_to_tc(59, 60) == "00:00:00:59"


def test_frames_to_tc_marker1_offset():
    """start_tc 01:00:00:00 at 60 fps = 216000 frames; +289 = 01:00:04:49."""
    start = _tc_to_frames("01:00:00:00", 60)
    assert start == 216000
    assert _frames_to_tc(216000 + 289, 60) == "01:00:04:49"


def test_frames_to_tc_marker2_offset():
    """start_tc + 36 frames → 01:00:00:36 (marker 2 begin=606ms → frame 36)."""
    start = _tc_to_frames("01:00:00:00", 60)
    # Reference Marker 2 is at begin_timestamp_ms=606 ms → frame 36 from recording start
    # but the reference file shows 01:00:10:06 which corresponds to a different begin_ms.
    # The reference shows Marker 2 at 01:00:10:06 → total_frames = 216000 + 10*60+6 = 216606
    # So begin_ms = (216606-216000)*1000/60 = 606*1000/60 = 10100 ms → verify round-trip
    tc = _frames_to_tc(start + 606, 60)
    assert tc == "01:00:10:06"


def test_frames_to_tc_marker3_offset():
    """Marker 3 is at 01:00:40:30; offset from start = 2430 frames."""
    start = _tc_to_frames("01:00:00:00", 60)
    assert _frames_to_tc(start + 2430, 60) == "01:00:40:30"


# ---------------------------------------------------------------------------
# _tc_to_frames
# ---------------------------------------------------------------------------


def test_tc_to_frames_zero():
    assert _tc_to_frames("00:00:00:00", 60) == 0


def test_tc_to_frames_one_hour():
    assert _tc_to_frames("01:00:00:00", 60) == 216000


def test_tc_to_frames_roundtrip():
    tc = "01:23:45:17"
    assert _frames_to_tc(_tc_to_frames(tc, 60), 60) == tc


def test_tc_to_frames_invalid():
    with pytest.raises(ValueError):
        _tc_to_frames("01:00:00", 60)


# ---------------------------------------------------------------------------
# _sanitize_marker_name
# ---------------------------------------------------------------------------


def test_sanitize_pipe():
    assert "|" not in _sanitize_marker_name("foo|bar")


def test_sanitize_cr_lf_tab():
    result = _sanitize_marker_name("foo\rbar\nbaz\tqux")
    assert "\r" not in result
    assert "\n" not in result
    assert "\t" not in result


def test_sanitize_collapse_whitespace():
    result = _sanitize_marker_name("foo   bar")
    assert result == "foo bar"


def test_sanitize_strip():
    assert _sanitize_marker_name("  hello  ") == "hello"


def test_sanitize_empty_fallback():
    assert _sanitize_marker_name("") == "Marker"


def test_sanitize_whitespace_only_fallback():
    assert _sanitize_marker_name("   \t\n  ") == "Marker"


def test_sanitize_pipe_only_fallback():
    assert _sanitize_marker_name("|||") == "Marker"


def test_sanitize_preserves_normal():
    assert _sanitize_marker_name("Marker 1") == "Marker 1"


# ---------------------------------------------------------------------------
# _category_color
# ---------------------------------------------------------------------------

_PALETTE = [
    "Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple", "Fuchsia",
    "Rose", "Lavender", "Sky", "Mint", "Lemon", "Sand", "Cocoa", "Cream",
]


def test_category_color_empty_string():
    assert _category_color("") == "Blue"


def test_category_color_none():
    assert _category_color(None) == "Blue"


def test_category_color_in_palette():
    color = _category_color("gameplay")
    assert color in _PALETTE


def test_category_color_deterministic():
    """Same category must give the same color across multiple calls."""
    assert _category_color("highlight") == _category_color("highlight")


def test_category_color_case_insensitive():
    """Category color is based on lowercased name."""
    assert _category_color("Bug") == _category_color("bug")
    assert _category_color("BUG") == _category_color("bug")


def test_category_color_stable_hash():
    """Color is determined by MD5 (stable across runs), not Python's salted hash."""
    # We can verify by re-deriving the expected value independently.
    import hashlib
    category = "gameplay"
    digest = hashlib.md5(category.lower().encode()).hexdigest()
    index = int(digest, 16) % 16
    expected = _PALETTE[index]
    assert _category_color(category) == expected


def test_category_color_different_categories():
    """Different categories should not all map to the same color (sanity check)."""
    colors = {_category_color(c) for c in ["alpha", "beta", "gamma", "delta", "epsilon"]}
    # With 16 colors and 5 categories, we expect at least 2 distinct colors
    # (extremely unlikely all 5 collide on the same slot).
    assert len(colors) >= 2


# ---------------------------------------------------------------------------
# markers_to_edl — byte-exact fidelity test (marker 1 against the reference EDL)
# ---------------------------------------------------------------------------


def test_markers_to_edl_single_marker_byte_exact():
    """Single-marker output matches the byte layout of the reference EDL exactly.

    The reference file (Timeline 1.markers.edl) has Marker 1 at 01:00:04:49,
    Blue color (empty category), D=1 (begin==end → clamped).
    We embed the expected string as a literal to avoid depending on the scratch file.
    """
    marker = {
        "begin_timestamp_ms": 4816,
        "timestamp_ms": 4816,
        "description": "Marker 1",
        "category": "",
    }
    expected = (
        "TITLE: Timeline 1.markers\r\n"
        "FCM: NON-DROP FRAME\r\n"
        "\r\n"
        "001  001      V     C        01:00:04:49 01:00:04:50 01:00:04:49 01:00:04:50  \r\n"
        " |C:ResolveColorBlue |M:Marker 1 |D:1\r\n"
        "\r\n"
    )
    result = markers_to_edl(
        [marker],
        fps=60,
        start_tc="01:00:00:00",
        title="Timeline 1.markers",
    )
    assert result == expected


def test_markers_to_edl_marker2_timecode():
    """Marker 2 at begin_ms=10100 ms, 60 fps → timecode 01:00:10:06."""
    # 10100 * 60 / 1000 = 606 frames; 216000+606=216606; 216606//60=3610s; 3610//60=60m 10s; 216606%60=6
    marker = {
        "begin_timestamp_ms": 10100,
        "timestamp_ms": 10100,
        "description": "Marker 2",
        "category": "",
    }
    result = markers_to_edl([marker], fps=60, start_tc="01:00:00:00", title="T")
    assert "01:00:10:06 01:00:10:07 01:00:10:06 01:00:10:07" in result


def test_markers_to_edl_marker3_timecode():
    """Marker 3 at begin_ms=40500 ms, 60 fps → timecode 01:00:40:30."""
    # 40500 * 60 / 1000 = 2430 frames; 216000+2430=218430; //60=3640s; 3640//60=60m 40s; 218430%60=30
    marker = {
        "begin_timestamp_ms": 40500,
        "timestamp_ms": 40500,
        "description": "Marker 3",
        "category": "",
    }
    result = markers_to_edl([marker], fps=60, start_tc="01:00:00:00", title="T")
    assert "01:00:40:30 01:00:40:31 01:00:40:30 01:00:40:31" in result


# ---------------------------------------------------------------------------
# markers_to_edl — structural properties
# ---------------------------------------------------------------------------


def test_markers_to_edl_crlf_only():
    """All line endings must be CRLF; no bare LF."""
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 1000, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    # Replace all CRLF then check no bare LF remains
    assert "\n" not in result.replace("\r\n", "")


def test_markers_to_edl_trailing_blank_line():
    """Output must end with a CRLF-terminated blank line (i.e., end with \\r\\n\\r\\n)."""
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    assert result.endswith("\r\n\r\n")


def test_markers_to_edl_event_prefix():
    """Event line must start with the fixed prefix."""
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    assert "001  001      V     C        " in result


def test_markers_to_edl_two_trailing_spaces():
    """Event line must end with two trailing spaces before CRLF."""
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    # The event line is the 4th line (0-indexed: TITLE, FCM, blank, event)
    lines = result.split("\r\n")
    event_line = lines[3]
    assert event_line.endswith("  ")


def test_markers_to_edl_comment_leading_space():
    """Comment line must begin with a single space."""
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    lines = result.split("\r\n")
    comment_line = lines[4]
    assert comment_line.startswith(" |C:")


def test_markers_to_edl_event_numbering():
    """Multiple markers produce sequential zero-padded event numbers."""
    markers = [
        {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "a", "category": ""},
        {"begin_timestamp_ms": 1000, "timestamp_ms": 1000, "description": "b", "category": ""},
        {"begin_timestamp_ms": 2000, "timestamp_ms": 2000, "description": "c", "category": ""},
    ]
    result = markers_to_edl(markers)
    assert "001  001      V     C        " in result
    assert "002  001      V     C        " in result
    assert "003  001      V     C        " in result


def test_markers_to_edl_blank_line_between_events():
    """A blank line (just CRLF) must separate consecutive events."""
    markers = [
        {"begin_timestamp_ms": 0, "timestamp_ms": 0, "description": "a", "category": ""},
        {"begin_timestamp_ms": 1000, "timestamp_ms": 1000, "description": "b", "category": ""},
    ]
    result = markers_to_edl(markers)
    # After first comment line there should be a blank CRLF before the second event
    assert " |D:1\r\n\r\n002" in result


def test_markers_to_edl_empty_list():
    """Empty marker list produces only the header."""
    result = markers_to_edl([])
    assert result == "TITLE: Checkpoint\r\nFCM: NON-DROP FRAME\r\n\r\n"


# ---------------------------------------------------------------------------
# markers_to_edl — D field (clip duration)
# ---------------------------------------------------------------------------


def test_markers_to_edl_d_clamp_to_one():
    """begin==end → D:1 (clamped from 0)."""
    marker = {"begin_timestamp_ms": 5000, "timestamp_ms": 5000, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    assert "|D:1" in result


def test_markers_to_edl_d_nonzero_duration():
    """30 000 ms at 60 fps = 1800 frames → D:1800."""
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 30_000,
        "description": "clip",
        "category": "",
    }
    result = markers_to_edl([marker])
    assert "|D:1800" in result


def test_markers_to_edl_d_rounds_correctly():
    """Duration rounds to nearest frame."""
    # 1008 ms * 60 / 1000 = 60.48 → round → 60
    marker = {"begin_timestamp_ms": 0, "timestamp_ms": 1008, "description": "x", "category": ""}
    result = markers_to_edl([marker])
    assert "|D:60" in result


# ---------------------------------------------------------------------------
# markers_to_edl — sanitization in output
# ---------------------------------------------------------------------------


def test_markers_to_edl_sanitizes_pipe_in_description():
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 0,
        "description": "foo|bar",
        "category": "",
    }
    result = markers_to_edl([marker])
    # The |M: field must not contain a literal | except as the field separator
    # Parse the comment line to isolate the |M: value
    lines = result.split("\r\n")
    comment = lines[4]
    # After "|M:" and before the next "|D:" there should be no pipe
    m_value = comment.split("|M:")[1].split(" |D:")[0]
    assert "|" not in m_value


def test_markers_to_edl_sanitizes_newline_in_description():
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 0,
        "description": "foo\nbar",
        "category": "",
    }
    result = markers_to_edl([marker])
    lines = result.split("\r\n")
    comment = lines[4]
    m_value = comment.split("|M:")[1].split(" |D:")[0]
    assert "\n" not in m_value and "\r" not in m_value


def test_markers_to_edl_sanitizes_tab_in_description():
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 0,
        "description": "foo\tbar",
        "category": "",
    }
    result = markers_to_edl([marker])
    lines = result.split("\r\n")
    comment = lines[4]
    m_value = comment.split("|M:")[1].split(" |D:")[0]
    assert "\t" not in m_value


# ---------------------------------------------------------------------------
# markers_to_edl — fps and start_tc variations
# ---------------------------------------------------------------------------


def test_markers_to_edl_fps_30():
    """At 30 fps, 1000 ms = 30 frames."""
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 1000,
        "description": "x",
        "category": "",
    }
    result = markers_to_edl([marker], fps=30, start_tc="00:00:00:00")
    assert "|D:30" in result


def test_markers_to_edl_nonzero_start_tc_offsets_markers():
    """start_tc shifts all marker timecodes."""
    marker = {
        "begin_timestamp_ms": 0,
        "timestamp_ms": 0,
        "description": "x",
        "category": "",
    }
    # With start_tc=00:00:05:00 at 60fps, offset=300 frames → 00:00:05:00
    result = markers_to_edl([marker], fps=60, start_tc="00:00:05:00")
    assert "00:00:05:00 00:00:05:01 00:00:05:00 00:00:05:01" in result


def test_markers_to_edl_start_tc_plus_begin():
    """Marker begin added to start_tc gives correct composite timecode."""
    marker = {
        "begin_timestamp_ms": 1000,  # 60 frames at 60fps
        "timestamp_ms": 1000,
        "description": "x",
        "category": "",
    }
    # start_tc=00:00:05:00 (300 frames) + 60 frames = 360 frames = 00:00:06:00
    result = markers_to_edl([marker], fps=60, start_tc="00:00:05:00")
    assert "00:00:06:00 00:00:06:01 00:00:06:00 00:00:06:01" in result


# ---------------------------------------------------------------------------
# markers_to_edl — default title
# ---------------------------------------------------------------------------


def test_markers_to_edl_default_title():
    result = markers_to_edl([])
    assert result.startswith("TITLE: Checkpoint\r\n")


def test_markers_to_edl_custom_title():
    result = markers_to_edl([], title="My Recording")
    assert result.startswith("TITLE: My Recording\r\n")


# ---------------------------------------------------------------------------
# Purity: no tkinter required
# ---------------------------------------------------------------------------


def test_resolve_export_no_tkinter(tmp_path):
    """Importing resolve_export must not require tkinter or a display."""
    # Run in a subprocess so we start with a clean import state (conftest pulls tkinter in).
    import subprocess

    script = (
        "import sys; "
        "import checkpoint.resolve_export; "
        'assert "tkinter" not in sys.modules, "tkinter was imported"; '
        'print("ok")'
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
