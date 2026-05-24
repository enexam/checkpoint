"""Shared pytest fixtures for the checkpoint test suite."""
import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def _tk_session_root():
    """One hidden tk.Tk root for the entire test session."""
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("No display available for Tk tests")
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass
