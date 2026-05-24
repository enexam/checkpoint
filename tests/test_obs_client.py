"""Tests for obs_client.py (task 2: OBS WebSocket client)."""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from checkpoint.obs_client import ObsClient


_BASE_CONFIG = {
    "obs_host": "localhost",
    "obs_port": 4455,
    "obs_password": "",
}


# get_snapshot() - None when unreachable

def test_get_snapshot_returns_none_when_not_connected():
    """get_snapshot() returns None when OBS is unreachable (not connected)."""
    client = ObsClient(_BASE_CONFIG)
    # _is_recording defaults to False, _req is None - should return None
    result = client.get_snapshot()
    assert result is None


def test_get_snapshot_returns_none_when_not_recording():
    """get_snapshot() returns None when connected but not recording."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = False
    client._req = MagicMock()  # simulate connected
    result = client.get_snapshot()
    assert result is None


# get_snapshot() - success path after RecordStateChanged

def _make_timecode_response(timecode: str) -> MagicMock:
    resp = MagicMock()
    resp.output_timecode = timecode
    return resp


def test_get_snapshot_returns_dict_when_recording():
    """get_snapshot() returns file_path and timestamp_ms when recording is active."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/obs_2024.mkv"

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = _make_timecode_response("00:01:30.500")
    client._req = mock_req

    result = client.get_snapshot()

    assert result is not None
    assert result["file_path"] == "C:/Videos/obs_2024.mkv"
    assert result["timestamp_ms"] == 90500  # 1m30.5s = 90500ms


def test_get_snapshot_timecode_conversion_hours():
    """get_snapshot() correctly converts HH:MM:SS.mmm timecodes spanning multiple hours."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/rec.mkv"

    mock_req = MagicMock()
    # 25:01:01.000 = 25*3600000 + 1*60000 + 1*1000 + 0 = 90061000 ms
    mock_req.get_record_status.return_value = _make_timecode_response("25:01:01.000")
    client._req = mock_req

    result = client.get_snapshot()

    assert result["timestamp_ms"] == 90061000


def test_get_snapshot_timecode_zero():
    """get_snapshot() handles 00:00:00.000 (start of recording)."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/rec.mkv"

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = _make_timecode_response("00:00:00.000")
    client._req = mock_req

    result = client.get_snapshot()

    assert result["timestamp_ms"] == 0


# get_snapshot() - mid-recording fallback (no _recording_file)

def test_get_snapshot_fallback_uses_newest_file(tmp_path):
    """get_snapshot() falls back to GetRecordDirectory + newest file when _recording_file is None."""
    # Create fake recording files with different mtimes
    old_file = tmp_path / "old.mkv"
    new_file = tmp_path / "new.mkv"
    old_file.write_text("x")
    time.sleep(0.05)
    new_file.write_text("x")

    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = None  # mid-recording start scenario

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = _make_timecode_response("00:00:05.000")
    dir_resp = MagicMock()
    dir_resp.record_directory = str(tmp_path)
    mock_req.get_record_directory.return_value = dir_resp
    client._req = mock_req

    result = client.get_snapshot()

    assert result is not None
    assert result["file_path"] == str(new_file)
    assert result["timestamp_ms"] == 5000


def test_get_snapshot_fallback_no_matching_files(tmp_path):
    """get_snapshot() returns None when fallback directory has no .mkv/.mp4/.flv files."""
    # Put a non-video file in the directory
    (tmp_path / "notes.txt").write_text("x")

    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = None

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = _make_timecode_response("00:00:05.000")
    dir_resp = MagicMock()
    dir_resp.record_directory = str(tmp_path)
    mock_req.get_record_directory.return_value = dir_resp
    client._req = mock_req

    result = client.get_snapshot()

    assert result is None


# get_snapshot() - exception safety

def test_get_snapshot_swallows_exception_from_req():
    """get_snapshot() returns None instead of raising when req call throws."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/rec.mkv"

    mock_req = MagicMock()
    mock_req.get_record_status.side_effect = RuntimeError("connection lost")
    client._req = mock_req

    result = client.get_snapshot()

    assert result is None


def test_get_snapshot_swallows_any_exception():
    """get_snapshot() returns None for any exception type including unexpected ones."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/rec.mkv"

    mock_req = MagicMock()
    mock_req.get_record_status.side_effect = Exception("unexpected")
    client._req = mock_req

    result = client.get_snapshot()

    assert result is None


# start() - non-blocking

def test_start_does_not_block():
    """start() returns immediately even when OBS connection would block/fail."""
    connect_started = threading.Event()
    connect_blocked = threading.Event()

    def slow_connect(*args, **kwargs):
        connect_started.set()
        connect_blocked.wait(timeout=2)
        raise ConnectionRefusedError("OBS not running")

    client = ObsClient(_BASE_CONFIG)

    with patch("checkpoint.obs_client.obsws_python.ReqClient", side_effect=slow_connect):
        t0 = time.monotonic()
        client.start()
        elapsed = time.monotonic() - t0

    # start() must return well under 1 second regardless of connection delay
    assert elapsed < 1.0

    connect_blocked.set()  # unblock the background thread
    client.stop()


# stop() - terminates background thread

def test_stop_terminates_thread():
    """stop() causes the background thread to exit within a reasonable timeout."""
    client = ObsClient(_BASE_CONFIG)

    with patch("checkpoint.obs_client.obsws_python.ReqClient", side_effect=ConnectionRefusedError):
        client.start()
        # Let the retry loop do at least one iteration
        time.sleep(0.05)
        client.stop()

    assert client._thread is None or not client._thread.is_alive()


# RecordStateChanged event handler

def test_record_state_changed_method_name_matches_obsws_convention():
    """Callback must be named on_record_state_changed (no underscore prefix).

    obsws_python resolves callbacks by matching __name__ to the event type via
    the on_{event_snake_case} convention. A leading underscore silently breaks
    registration so events are never received.
    """
    client = ObsClient(_BASE_CONFIG)
    assert hasattr(client, "on_record_state_changed"), (
        "Method must be named on_record_state_changed - obsws_python callback "
        "registration matches by __name__ and rejects leading underscores"
    )
    assert not hasattr(client, "_on_record_state_changed"), (
        "_on_record_state_changed must not exist; obsws_python won't register it"
    )


def test_record_state_changed_started_updates_state():
    """on_record_state_changed() sets _is_recording=True and stores the file path."""
    client = ObsClient(_BASE_CONFIG)

    event = MagicMock()
    event.output_active = True
    event.output_path = "C:/Videos/new_rec.mkv"

    client.on_record_state_changed(event)

    assert client._is_recording is True
    assert client._recording_file == "C:/Videos/new_rec.mkv"


def test_record_state_changed_stopped_updates_state():
    """on_record_state_changed() sets _is_recording=False when recording stops."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True
    client._recording_file = "C:/Videos/rec.mkv"

    event = MagicMock()
    event.output_active = False
    event.output_path = ""

    client.on_record_state_changed(event)

    assert client._is_recording is False


# _connect() - initial state sync

def test_connect_syncs_initial_recording_state():
    """_connect() must call get_record_status() to sync state when OBS is already recording.

    Without this query, starting the app while OBS is already recording leaves
    _is_recording=False and get_snapshot() always returns None until the next
    RecordStateChanged event (which never fires for an in-progress recording).
    """
    client = ObsClient(_BASE_CONFIG)

    mock_status = MagicMock()
    mock_status.output_active = True

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = mock_status

    mock_evt = MagicMock()

    with patch("checkpoint.obs_client.obsws_python.ReqClient", return_value=mock_req), \
         patch("checkpoint.obs_client.obsws_python.EventClient", return_value=mock_evt):
        client._connect()

    mock_req.get_record_status.assert_called_once()
    assert client._is_recording is True


def test_connect_syncs_not_recording_state():
    """_connect() sets _is_recording=False when OBS reports output_active=False."""
    client = ObsClient(_BASE_CONFIG)
    client._is_recording = True  # stale state from a previous session

    mock_status = MagicMock()
    mock_status.output_active = False

    mock_req = MagicMock()
    mock_req.get_record_status.return_value = mock_status

    mock_evt = MagicMock()

    with patch("checkpoint.obs_client.obsws_python.ReqClient", return_value=mock_req), \
         patch("checkpoint.obs_client.obsws_python.EventClient", return_value=mock_evt):
        client._connect()

    assert client._is_recording is False
