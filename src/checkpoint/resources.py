"""Resource path helpers for dev and frozen (PyInstaller) environments."""
import sys
import tkinter as tk
from pathlib import Path


def resource_path(rel: str) -> Path:
    """Return the absolute path to a package resource.

    In a frozen PyInstaller bundle, resources are extracted to ``sys._MEIPASS``
    under a ``checkpoint/`` subdirectory. In a normal dev install, they live
    alongside this file in the package directory.

    Parameters
    ----------
    rel:
        Relative path from the package root (e.g. ``"assets/icon.png"``).

    Returns
    -------
    Path
        Absolute path to the resource. The file may not exist; callers must
        check ``.exists()`` before opening.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return Path(meipass) / "checkpoint" / rel
    return Path(__file__).parent / rel


def icon_png_path() -> Path:
    """Return the path to ``assets/icon.png`` (may not exist)."""
    return resource_path("assets/icon.png")


def icon_ico_path() -> Path:
    """Return the path to ``assets/icon.ico`` (may not exist)."""
    return resource_path("assets/icon.ico")


def set_window_icon(win: tk.BaseWidget) -> None:
    """Apply the application icon to a Tk window if the assets exist.

    Sets ``iconphoto`` from ``icon.png`` when present, and ``iconbitmap``
    from ``icon.ico`` when present and running on Windows. Silently does
    nothing when either asset is absent or when a ``TclError`` is raised
    (e.g. in headless environments).

    A reference to the ``PhotoImage`` is stored on the window as
    ``_icon_photo`` to prevent garbage collection.
    """
    try:
        png = icon_png_path()
        if png.exists():
            photo = tk.PhotoImage(file=str(png))
            win._icon_photo = photo  # type: ignore[attr-defined]
            win.iconphoto(False, photo)  # type: ignore[attr-defined]

        ico = icon_ico_path()
        if ico.exists() and sys.platform == "win32":
            try:
                win.iconbitmap(str(ico))  # type: ignore[attr-defined]
            except tk.TclError:
                pass
    except tk.TclError:
        pass
    except Exception:
        pass
