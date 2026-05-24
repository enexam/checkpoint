"""OBS WebSocket client with persistent connection and recording-state tracking.

Connects to OBS Studio via obs-websocket v5 (obsws-python). Maintains a
background thread that retries the connection every 5 s on failure.
Tracks the active recording file path via RecordStateChanged events and
exposes get_snapshot() for hotkey callbacks.
"""
import logging
import threading
from pathlib import Path

import obsws_python


def _timecode_to_ms(timecode: str) -> int:
    """Convert an OBS timecode string (HH:MM:SS.mmm) to milliseconds."""
    # timecode format: "HH:MM:SS.mmm"
    hms, ms_str = timecode.split(".")
    h, m, s = (int(x) for x in hms.split(":"))
    ms = int(ms_str)
    return (h * 3600 + m * 60 + s) * 1000 + ms


class ObsClient:
    """Persistent OBS WebSocket client.

    Call start() to begin connecting in the background, stop() to shut down.
    get_snapshot() returns recording state at the moment of the call.
    """

    def __init__(self, config: dict) -> None:
        self._host: str = config.get("obs_host", "localhost")
        self._port: int = config.get("obs_port", 4455)
        self._password: str = config.get("obs_password", "")

        self._is_recording: bool = False
        self._recording_file: str | None = None

        self._req: obsws_python.ReqClient | None = None
        self._evt: obsws_python.EventClient | None = None

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # Public API

    def start(self) -> None:
        """Start the background connection thread (non-blocking)."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="obs-client")
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        self._disconnect()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def get_snapshot(self) -> dict | None:
        """Return current recording snapshot or None.

        Returns None if OBS is unreachable, not recording, or any error occurs.
        On success returns {"file_path": str, "timestamp_ms": int}.
        """
        try:
            if not self._is_recording or self._req is None:
                return None

            status = self._req.get_record_status()
            timestamp_ms = _timecode_to_ms(status.output_timecode)

            file_path = self._recording_file
            if file_path is None:
                file_path = self._fallback_file_path()
            if file_path is None:
                return None

            return {"file_path": file_path, "timestamp_ms": timestamp_ms}
        except Exception:
            return None

    # Internal

    def _run(self) -> None:
        """Background loop: connect, then retry every 5 s on failure."""
        while not self._stop_event.is_set():
            try:
                self._connect()
                self._stop_event.wait()
            except Exception as exc:
                logging.warning("OBS connection failed: %s - retrying in 5 s", exc)
                self._disconnect()
                self._stop_event.wait(5)

    def _connect(self) -> None:
        """Establish ReqClient and EventClient connections."""
        kwargs = {
            "host": self._host,
            "port": self._port,
            "password": self._password,
        }
        self._req = obsws_python.ReqClient(**kwargs)
        self._evt = obsws_python.EventClient(**kwargs)
        self._evt.callback.register(self.on_record_state_changed)
        # Sync initial state - RecordStateChanged is missed if OBS was already
        # recording before this connection was established.
        status = self._req.get_record_status()
        self._is_recording = bool(status.output_active)
        logging.info("OBS connected - recording=%s", self._is_recording)

    def _disconnect(self) -> None:
        """Disconnect both clients, ignoring any errors."""
        for client in (self._evt, self._req):
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass
        self._req = None
        self._evt = None

    def on_record_state_changed(self, event) -> None:
        """EventClient callback - updates recording state."""
        self._is_recording = bool(event.output_active)
        if event.output_active:
            self._recording_file = event.output_path or None
        logging.info("OBS RecordStateChanged - recording=%s file=%s", self._is_recording, self._recording_file)

    def _fallback_file_path(self) -> str | None:
        """Return the newest .mkv/.mp4/.flv file in GetRecordDirectory."""
        try:
            resp = self._req.get_record_directory()
            directory = Path(resp.record_directory)
            candidates = [
                f for ext in ("*.mkv", "*.mp4", "*.flv")
                for f in directory.glob(ext)
            ]
            if not candidates:
                return None
            return str(max(candidates, key=lambda p: p.stat().st_mtime))
        except Exception:
            return None
