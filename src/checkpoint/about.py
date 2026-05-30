"""About tab and reporting utilities for Checkpoint."""
import os
import platform
import webbrowser
from pathlib import Path
from tkinter import ttk
import urllib.parse

REPO_URL = "https://github.com/enexam/checkpoint"


def data_dir() -> Path:
    """Return the Checkpoint application data directory (%APPDATA%/Checkpoint)."""
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "Checkpoint"


def build_issue_url(kind: str) -> str:
    """Build a GitHub new-issue URL pre-filled for a bug or feature report.

    Parameters
    ----------
    kind:
        ``"bug"`` for a bug report, ``"feature"`` for a feature request.

    Returns
    -------
    str
        A fully-formed URL string.
    """
    import checkpoint

    if kind == "bug":
        title_prefix = "[Bug] "
        label = "bug"
        body = (
            "## Describe the bug\n\n"
            "\n\n"
            "## Steps to reproduce\n\n"
            "\n\n"
            "## Environment\n\n"
            f"- Checkpoint version: {checkpoint.__version__}\n"
            f"- OS: {platform.platform()}\n"
            f"- Python: {platform.python_version()}"
        )
    else:
        title_prefix = "[Feature] "
        label = "enhancement"
        body = (
            "## Feature request\n\n"
            "\n\n"
            "## Why would this be useful?\n\n"
        )

    params = urllib.parse.urlencode(
        {"title": title_prefix, "body": body, "labels": label},
        quote_via=urllib.parse.quote,
    )
    return f"{REPO_URL}/issues/new?{params}"


def build_about_tab(parent: ttk.Frame) -> None:
    """Populate *parent* with the About tab content.

    Parameters
    ----------
    parent:
        The frame to build the About UI inside.
    """
    import checkpoint

    # Title
    ttk.Label(
        parent,
        text=f"Checkpoint v{checkpoint.__version__}",
        font=("TkDefaultFont", 14, "bold"),
    ).pack(pady=(16, 4))

    # One-line description
    ttk.Label(
        parent,
        text="Hotkey-driven clip marker tool bridging OBS Studio and DaVinci Resolve.",
    ).pack(pady=(0, 4))

    # License
    ttk.Label(parent, text="Licensed under GPL-3.0").pack(pady=(0, 4))

    # Author
    ttk.Label(parent, text='by Maxence "Enexam" Beuselinck').pack(pady=(0, 12))

    # Action buttons
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(pady=(0, 12))

    ttk.Button(
        btn_frame,
        text="GitHub Repository",
        command=lambda: webbrowser.open(REPO_URL),
    ).grid(row=0, column=0, padx=4, pady=4)

    ttk.Button(
        btn_frame,
        text="Report a Bug",
        command=lambda: webbrowser.open(build_issue_url("bug")),
    ).grid(row=0, column=1, padx=4, pady=4)

    ttk.Button(
        btn_frame,
        text="Request a Feature",
        command=lambda: webbrowser.open(build_issue_url("feature")),
    ).grid(row=0, column=2, padx=4, pady=4)

    def _open_data_folder() -> None:
        if hasattr(os, "startfile"):
            os.startfile(data_dir())

    ttk.Button(
        btn_frame,
        text="Open Data Folder",
        command=_open_data_folder,
    ).grid(row=1, column=0, padx=4, pady=4)
