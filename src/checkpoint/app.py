"""Main application: systray icon, global hotkey, and orchestration."""
import ctypes
import ctypes.wintypes
import logging
import os
import queue as _queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image, ImageDraw, ImageFont

from checkpoint.categories import load_categories, save_categories
from checkpoint.config import load_config, save_config
from checkpoint.obs_client import ObsClient
from checkpoint.popup import show_popup
from checkpoint.main_window import notify_new_marker, open_main_window
from checkpoint.storage import append_marker, init_db

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_NOREPEAT = 0x4000
_MOD_CONTROL = 0x0002

_FKEY_VK = {f"f{i}": 0x6F + i for i in range(1, 13)}  # f1=0x70 … f12=0x7B


def _parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parse 'ctrl+f9' into (modifiers, vk_code) for RegisterHotKey."""
    mods = _MOD_NOREPEAT
    vk = None
    for part in (p.strip().lower() for p in hotkey_str.split("+")):
        if part == "ctrl":
            mods |= _MOD_CONTROL
        elif part == "alt":
            mods |= 0x0001
        elif part == "shift":
            mods |= 0x0004
        elif part == "win":
            mods |= 0x0008
        else:
            vk = _FKEY_VK.get(part)
    if vk is None:
        raise ValueError(f"unrecognised key in hotkey string: {hotkey_str!r}")
    return mods, vk


class _HotkeyListener:
    """Registers a global hotkey via RegisterHotKey and pumps WM_HOTKEY messages."""

    _HOTKEY_ID = 1

    def __init__(self, hotkey_str: str, callback: Callable) -> None:
        self._mods, self._vk = _parse_hotkey(hotkey_str)
        self._callback = callback
        self._thread_id: int | None = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, _WM_QUIT, 0, 0
            )

    def update_hotkey(self, hotkey_str: str) -> None:
        """Stop the current hotkey thread, parse the new hotkey, and start a fresh thread."""
        self.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._mods, self._vk = _parse_hotkey(hotkey_str)
        self._thread_id = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey")
        self._thread.start()

    def _run(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        ok = ctypes.windll.user32.RegisterHotKey(
            None, self._HOTKEY_ID, self._mods, self._vk
        )
        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            logging.error("RegisterHotKey failed - Windows error %d", err)
            return
        logging.info("hotkey registered (vk=0x%02x mods=0x%x)", self._vk, self._mods)
        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == _WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                self._callback()
        ctypes.windll.user32.UnregisterHotKey(None, self._HOTKEY_ID)
        logging.info("hotkey unregistered")


def _make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), color=(0x1A, 0x1A, 0x2E, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    draw.text((32, 32), "C", fill="white", font=font, anchor="mm")
    return img


def _preset_string(duration_hint_ms: int) -> str:
    """Derive a preset string from a duration in milliseconds.

    Returns one of "10s", "30s", "1m", "3m", "5m", or "custom:N" where N is
    the number of whole seconds.
    """
    _canonical = {10_000: "10s", 30_000: "30s", 60_000: "1m", 180_000: "3m", 300_000: "5m"}
    return _canonical.get(duration_hint_ms, f"custom:{duration_hint_ms // 1000}")


def _make_hotkey_callback(
    obs: ObsClient,
    categories: list[str],
    show_popup_fn: Callable,
    append_marker_fn: Callable,
    save_cats_fn: Callable,
    config: dict,
    save_config_fn: Callable,
) -> Callable:
    def _on_hotkey() -> None:
        logging.debug("hotkey fired")
        snapshot = obs.get_snapshot()
        if snapshot is None:
            logging.debug("OBS not recording - skipping")
            return
        logging.debug("OBS recording: %s @ %d ms", snapshot["file_path"], snapshot["timestamp_ms"])
        initial_preset = config.get("last_duration_preset", "30s")
        result = show_popup_fn(categories, initial_preset)
        if result is None:
            logging.debug("popup cancelled")
            return
        description, category, duration_hint_ms = result
        end_ms = snapshot["timestamp_ms"]
        begin_ms = max(0, end_ms - duration_hint_ms)
        logging.info(
            "marker: %r [%s] @ %d ms (begin=%d, duration=%d ms)",
            description, category, end_ms, begin_ms, duration_hint_ms,
        )
        append_marker_fn(snapshot["file_path"], end_ms, description, category, begin_ms, duration_hint_ms)
        config["last_duration_preset"] = _preset_string(duration_hint_ms)
        save_config_fn(config)
        if category and category not in categories:
            categories.append(category)
            save_cats_fn(categories)

    return _on_hotkey


def _setup_logging() -> None:
    log_path = (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Checkpoint"
        / "checkpoint.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    logging.info("Checkpoint starting")


def main() -> None:
    _setup_logging()
    ctypes.windll.kernel32.SetConsoleTitleW("Checkpoint")
    init_db()
    config = load_config()
    categories = load_categories()

    obs = ObsClient(config)
    obs.start()

    root = tk.Tk()
    root.withdraw()
    root.title("Checkpoint")
    pending: _queue.Queue = _queue.Queue()

    hotkey_str = config.get("hotkey", "ctrl+f9")
    logging.info("registering hotkey: %s", hotkey_str)
    callback = _make_hotkey_callback(obs, categories, show_popup, append_marker, save_categories, config, save_config)

    def _on_hotkey() -> None:
        pending.put(True)

    listener = _HotkeyListener(hotkey_str, _on_hotkey)
    listener.start()

    def _open(icon: pystray.Icon, _item: object) -> None:
        def _quit_app() -> None:
            icon.stop()
            root.quit()
        root.after(0, lambda: open_main_window(root, config, listener, obs, categories=categories, on_quit=_quit_app))

    def _quit(icon: pystray.Icon, _item: object) -> None:
        icon.stop()
        root.quit()

    icon = pystray.Icon(
        "Checkpoint",
        _make_icon_image(),
        title="Checkpoint",
        menu=pystray.Menu(
            pystray.MenuItem("Open Checkpoint", _open),
            pystray.MenuItem("Quit", _quit),
        ),
    )

    def _poll() -> None:
        try:
            pending.get_nowait()
            callback()
            notify_new_marker()
        except _queue.Empty:
            pass
        root.after(50, _poll)

    logging.info("systray running")
    root.after(50, _poll)
    icon.run_detached()
    root.mainloop()

    listener.stop()
    obs.stop()
