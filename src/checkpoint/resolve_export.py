"""DaVinci Resolve marker EDL export.

Public API
----------
markers_to_edl(markers, fps, start_tc, title) -> str
    Convert a list of marker dicts to a Resolve-compatible marker EDL string.

Each marker dict must contain:
    begin_timestamp_ms  int  – clip start, ms from recording start
    timestamp_ms        int  – clip end (hotkey stamp), ms from recording start
    description         str  – free-text label
    category            str  – user category (may be "" or None)

The output uses CRLF line endings and matches the byte layout of a real EDL
exported from DaVinci Resolve (NON-DROP FRAME, integer fps).
"""

from __future__ import annotations

import hashlib
import re

__all__ = ["markers_to_edl"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RESOLVE_COLORS: list[str] = [
    "Blue",
    "Cyan",
    "Green",
    "Yellow",
    "Red",
    "Pink",
    "Purple",
    "Fuchsia",
    "Rose",
    "Lavender",
    "Sky",
    "Mint",
    "Lemon",
    "Sand",
    "Cocoa",
    "Cream",
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _ms_to_frames(ms: int | float, fps: int) -> int:
    """Convert milliseconds to frame count using round-half-even."""
    return round(ms * fps / 1000)


def _frames_to_tc(frames: int, fps: int) -> str:
    """Convert an absolute frame count to ``HH:MM:SS:FF`` timecode (NON-DROP)."""
    ff = frames % fps
    total_seconds = frames // fps
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _tc_to_frames(tc: str, fps: int) -> int:
    """Parse ``HH:MM:SS:FF`` timecode into an absolute frame count (NON-DROP)."""
    parts = tc.split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode: {tc!r}")
    hh, mm, ss, ff = (int(p) for p in parts)
    return ((hh * 60 + mm) * 60 + ss) * fps + ff


def _sanitize_marker_name(s: str) -> str:
    """Sanitize a marker name for use in the ``|M:`` EDL field.

    Replaces ``|``, CR, LF, and TAB with a single space, collapses runs of
    whitespace, strips leading/trailing whitespace, and falls back to
    ``"Marker"`` if the result is empty.
    """
    # Replace forbidden characters with space
    cleaned = re.sub(r"[|\r\n\t]", " ", s)
    # Collapse runs of whitespace to a single space and strip
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else "Marker"


def _category_color(category: str | None) -> str:
    """Return a Resolve color name for the given category.

    Empty or None → ``"Blue"``.
    Non-empty → deterministic stable pick from the 16-color palette based on
    an MD5 hash of the lowercased category name (not Python's salted hash).
    """
    if not category:
        return "Blue"
    digest = hashlib.md5(category.lower().encode()).hexdigest()
    index = int(digest, 16) % len(_RESOLVE_COLORS)
    return _RESOLVE_COLORS[index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def markers_to_edl(
    markers: list[dict],
    fps: int = 60,
    start_tc: str = "01:00:00:00",
    title: str = "Checkpoint",
) -> str:
    """Build a DaVinci Resolve marker EDL string from a list of marker dicts.

    Parameters
    ----------
    markers:
        List of dicts with keys ``begin_timestamp_ms``, ``timestamp_ms``,
        ``description``, ``category``.
    fps:
        Integer frames-per-second of the target Resolve timeline.
    start_tc:
        Timeline start timecode in ``HH:MM:SS:FF`` format (default ``01:00:00:00``).
    title:
        EDL title written in the ``TITLE:`` header line.

    Returns
    -------
    str
        Complete EDL text with CRLF line endings.
    """
    global_start = _tc_to_frames(start_tc, fps)

    lines: list[str] = []

    # Header
    lines.append(f"TITLE: {title}\r\n")
    lines.append("FCM: NON-DROP FRAME\r\n")
    lines.append("\r\n")

    for n, marker in enumerate(markers, start=1):
        begin_ms: int = marker["begin_timestamp_ms"]
        end_ms: int = marker["timestamp_ms"]
        description: str = marker.get("description", "") or ""
        category: str | None = marker.get("category") or None

        # Timecode for the marker position (start_tc + begin)
        begin_frames = global_start + _ms_to_frames(begin_ms, fps)
        src_in = _frames_to_tc(begin_frames, fps)
        src_out = _frames_to_tc(begin_frames + 1, fps)

        # Clip duration in frames for |D:
        duration_frames = max(1, _ms_to_frames(end_ms - begin_ms, fps))

        # Sanitized name and color
        name = _sanitize_marker_name(description)
        color = _category_color(category)

        # Event line: prefix + "srcIn srcOut recIn recOut" + 2 trailing spaces
        prefix = f"{n:03d}  001      V     C        "
        event_line = f"{prefix}{src_in} {src_out} {src_in} {src_out}  \r\n"
        comment_line = f" |C:ResolveColor{color} |M:{name} |D:{duration_frames}\r\n"

        lines.append(event_line)
        lines.append(comment_line)
        lines.append("\r\n")

    return "".join(lines)
