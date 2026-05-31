"""Tests for resources.py."""
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pytest

import checkpoint


def test_resource_path_name():
    """resource_path('foo').name == 'foo'."""
    from checkpoint.resources import resource_path
    assert resource_path("foo").name == "foo"


def test_resource_path_under_package_in_dev():
    """In dev (non-frozen), resource_path returns a path under the checkpoint package dir."""
    from checkpoint.resources import resource_path
    import checkpoint.resources as _mod
    pkg_dir = Path(_mod.__file__).parent
    result = resource_path("some/thing")
    assert result == pkg_dir / "some" / "thing"


def test_resource_path_frozen(tmp_path):
    """In a frozen env (sys._MEIPASS set), resource_path uses _MEIPASS/checkpoint/."""
    from checkpoint.resources import resource_path
    with patch("sys._MEIPASS", str(tmp_path), create=True):
        # Also patch getattr so _MEIPASS is detected.
        import sys
        original = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = str(tmp_path)  # type: ignore[attr-defined]
        try:
            result = resource_path("assets/icon.png")
            assert result == tmp_path / "checkpoint" / "assets" / "icon.png"
        finally:
            if original is None:
                del sys._MEIPASS
            else:
                sys._MEIPASS = original  # type: ignore[attr-defined]


def test_icon_png_path_name():
    """icon_png_path().name == 'icon.png'."""
    from checkpoint.resources import icon_png_path
    assert icon_png_path().name == "icon.png"


def test_icon_ico_path_name():
    """icon_ico_path().name == 'icon.ico'."""
    from checkpoint.resources import icon_ico_path
    assert icon_ico_path().name == "icon.ico"


_MISSING = Path(__file__).parent / "_no_such_dir"


def test_set_window_icon_no_op_when_assets_absent(_tk_session_root):
    """set_window_icon does not raise when no assets exist."""
    from checkpoint.resources import set_window_icon
    win = tk.Toplevel(_tk_session_root)
    try:
        with patch("checkpoint.resources.icon_png_path", return_value=_MISSING / "icon.png"), \
             patch("checkpoint.resources.icon_ico_path", return_value=_MISSING / "icon.ico"):
            set_window_icon(win)  # must not raise
    finally:
        win.destroy()


def test_set_window_icon_no_op_with_mock():
    """set_window_icon is a safe no-op when the icon assets are absent."""
    from unittest.mock import MagicMock
    from checkpoint.resources import set_window_icon
    # Simulate missing assets so the premise holds regardless of repo contents.
    mock_win = MagicMock()
    with patch("checkpoint.resources.icon_png_path", return_value=_MISSING / "icon.png"), \
         patch("checkpoint.resources.icon_ico_path", return_value=_MISSING / "icon.ico"):
        set_window_icon(mock_win)
    # iconphoto and iconbitmap should NOT have been called (no assets present).
    mock_win.iconphoto.assert_not_called()
    mock_win.iconbitmap.assert_not_called()


def test_make_icon_image_still_64x64_rgba():
    """_make_icon_image() returns a 64x64 RGBA image (no icon.png present)."""
    from checkpoint.app import _make_icon_image
    img = _make_icon_image()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_version_attribute():
    """checkpoint.__version__ is accessible and equals '0.0.0'."""
    assert checkpoint.__version__ == "0.0.0"
