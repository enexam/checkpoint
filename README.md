# Checkpoint

Checkpoint is an app that fits between OBS Studio and DaVinci Resolve in a video content creation workflow. It simplifies derushing over long desktop recordings by allowing you from the press of a hotkey to stamp timestamped markers (video file + timestamp + description + category) into a CSV file alongside your recording. You can then explore, organize, and export these markers.

## Installation and Usage

### Requirements

- Windows 10 or later
- Python 3.11 or later
- OBS Studio 28+ with WebSocket server enabled (OBS → Tools → WebSocket Server Settings)

### Installation

1. Clone or download this repository.
2. Install Python dependencies:
   ```
   pip install -e .
   ```
   Or, if using a virtual environment:
   ```
   python -m venv venv
   .\venv\Scripts\activate
   pip install -e .
   ```

### Running the App

Run the app with:
```
python -m checkpoint
```

The Checkpoint icon appears in the system tray. The app runs in the background and listens for the hotkey.

### The Hotkey

By default, the hotkey is **Ctrl+F9**. You can change it by editing the configuration file (see Configuration below).

When you press the hotkey:
- If OBS is not recording, nothing happens.
- If OBS is recording, a popup window appears. Fill in:
  - **Description** (required, non-empty)
  - **Category** (optional; you can type freely or select from previously used categories)
- Click **OK** to save the marker, or **Cancel** to dismiss without saving.

The marker is written to a CSV file placed in the same directory as the recording file.

### Configuration

Configuration is stored in `%APPDATA%\Checkpoint\config.json`. On first run, this file is created with defaults:

```json
{
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "",
  "hotkey": "<ctrl>+f9"
}
```

You can edit this file to:
- **obs_host**: hostname or IP of the OBS WebSocket server (default: localhost)
- **obs_port**: port of the OBS WebSocket server (default: 4455)
- **obs_password**: WebSocket server password if set (default: empty)
- **hotkey**: global hotkey string (default: `<ctrl>+f9`; use pynput syntax, e.g., `<alt>+<shift>+c`)

After editing the config file, restart the app for changes to take effect.

### Data Storage

#### CSV Markers

When you press the hotkey during a recording and confirm the popup, one row is appended to a CSV file. The CSV file is placed alongside the recording file with the same name stem + `_markers.csv`.

Example:
- Recording: `C:\Videos\recording_2026_05_24.mkv`
- Markers CSV: `C:\Videos\recording_2026_05_24_markers.csv`

The CSV has these columns:
- **file_path**: Path to the recording file
- **timestamp_ms**: Timestamp in milliseconds since the recording started
- **timestamp_hms**: Timestamp formatted as HH:MM:SS.mmm (hours may exceed 23 for long recordings)
- **description**: Your description text
- **category**: Category (may be empty)

Example CSV row:
```
C:\Videos\recording_2026_05_24.mkv,90061000,25:01:01.000,Good take,editing
```

#### Known Categories

Previously used categories are stored in `%APPDATA%\Checkpoint\categories.json`. This file is created automatically and updated whenever you enter a new category in the popup.
