# Checkpoint

Checkpoint is an app that fits between OBS Studio and DaVinci Resolve in a video content creation workflow. It simplifies derushing over long desktop recordings by allowing you to press a hotkey during recording to stamp timestamped markers (video file + timestamp + description + category) into a local SQLite database. You can then explore, organize, and export these markers via a graphical interface.

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

The Checkpoint icon appears in the system tray. The app runs in the background and listens for the hotkey. Click "Open Checkpoint" in the system tray menu to open the main window, where you can configure settings, view and filter markers, and export them.

### The Hotkey

By default, the hotkey is **Ctrl+F9**. You can change it by editing the configuration file (see Configuration below).

When you press the hotkey:
- If OBS is not recording, nothing happens.
- If OBS is recording, a popup window appears. Fill in:
  - **Description** (required, non-empty)
  - **Category** (optional; you can type freely or select from previously used categories)
- Click **OK** to save the marker, or **Cancel** to dismiss without saving.

The marker is recorded in the SQLite database.

### Main Window

Click "Open Checkpoint" in the system tray menu to open the main window. The window has two tabs:

#### Settings Tab

- **Hotkey**: Change the global hotkey. Changes take effect immediately.
- **OBS Connection**: Configure the OBS WebSocket server hostname, port, and password. Changes take effect immediately and reconnect the client.
- **Categories**: View, add, and manage categories. New categories appear immediately in the hotkey popup.

#### Markers Tab

- **Filter**: Filter markers by recording file and/or category. Use the "All" option to see all markers.
- **Refresh**: Reload markers from the database based on the current filters.
- **Select All / Unselect All**: Quickly select or deselect all visible (filtered) markers.
- **Export to CSV**: Export the selected markers to a CSV file. A file dialog will appear to let you choose where to save the file.

### Configuration

Configuration is stored in `%APPDATA%\Checkpoint\config.json`. On first run, this file is created with defaults:

```json
{
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "",
  "hotkey": "ctrl+f9"
}
```

You can configure these settings via the Settings tab in the main window:
- **obs_host**: hostname or IP of the OBS WebSocket server (default: localhost)
- **obs_port**: port of the OBS WebSocket server (default: 4455)
- **obs_password**: WebSocket server password if set (default: empty)
- **hotkey**: global hotkey string (default: `ctrl+f9`; use syntax like `ctrl+f9`, `alt+shift+c`, etc.)

Changes made in the Settings tab take effect immediately without restarting the app. You can also manage categories in the Settings tab; they are automatically suggested in the hotkey popup.

### Data Storage

#### SQLite Database

All markers are stored in a single SQLite database at `%APPDATA%\Checkpoint\markers.db`. When you press the hotkey during a recording and confirm the popup, a row is inserted with the following information:

- **file_path**: Path to the recording file
- **timestamp_ms**: Timestamp in milliseconds since the recording started
- **timestamp_hms**: Timestamp formatted as HH:MM:SS.mmm (hours may exceed 23 for long recordings)
- **description**: Your description text
- **category**: Category (may be empty)
- **created_at**: Timestamp when the marker was created

You can view, filter, and export markers from the Markers tab in the main window.

#### Marker Export

You can export selected markers to CSV from the Markers tab. The exported CSV uses the same schema as above (file_path, timestamp_ms, timestamp_hms, description, category) and can be imported into other tools or analysis pipelines.

#### Known Categories

Previously used categories are stored in `%APPDATA%\Checkpoint\categories.json`. This file is created automatically and updated whenever you enter a new category in the popup or via the Settings tab.
