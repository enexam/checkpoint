# Checkpoint

Checkpoint is an app that fits between OBS Studio and DaVinci Resolve in a video content creation workflow. It simplifies derushing over long desktop recordings by allowing you to press a hotkey during recording to stamp timestamped markers (video file + timestamp + description + category) into a local SQLite database. You can then explore, organize, and export these markers via a graphical interface.

## Installation and Usage

### User Installation

**Requirements:**
- Windows 10 or later
- OBS Studio 28+ with WebSocket server enabled (OBS → Tools → WebSocket Server Settings)
- (Optional) VLC media player for video preview in Clip Explorer

Download `checkpoint.exe` from the [Releases page](https://github.com/enexam/checkpoint/releases) and run it.
The Checkpoint icon appears in the system tray. The app runs in the background and listens for the hotkey. Click "Open Checkpoint" in the system tray menu to open the main window, where you can configure settings, view and filter markers, and export them.

---

### Development Setup

**Requirements:**
- Windows 10 or later
- Python 3.11 or later
- OBS Studio 28+ with WebSocket server enabled
- (Optional) VLC media player for video preview in Clip Explorer

**Python dependencies** (installed automatically via pip):
- `obsws-python` - OBS WebSocket client
- `pystray` - system tray icon
- `Pillow` - image handling for the tray icon

1. Clone the repository:
   ```
   git clone https://github.com/enexam/checkpoint.git
   cd checkpoint
   ```
2. Install in editable mode:
   ```
   pip install -e .
   ```
3. Run the app:
   ```
   python -m checkpoint
   ```

### Hotkey

By default, the hotkey is **Ctrl+F9**. You can change it by editing the configuration file (see Configuration below).

When you press the hotkey:
- If OBS is not recording, a notification balloon appears in the system tray saying "OBS is not recording".
- If OBS is recording, a popup window appears. Fill in:
  - **Description** (required, non-empty)
  - **Category** (optional; you can type freely or select from previously used categories)
  - **Duration** (presets: 10s, 30s, 1m, 3m, 5m, or Custom; default is 30s). The hotkey timestamp marks the clip end; the duration is subtracted to compute the begin timestamp.
- Click **OK** to save the marker, or **Cancel** to dismiss without saving.

The marker is recorded in the SQLite database. Your last-used duration preset is saved and restored on the next hotkey popup.

### Main Window and Clip Explorer

Right-clicking the system tray icon opens a menu with these items:

- **Open Checkpoint**: open the main window (Settings, Markers, and About tabs).
- **Open Clip Explorer**: open the Clip Explorer window.
- **About**: open the main window focused on the About tab.
- **Report a Bug**: open the main window focused on the About tab (where the Report a Bug / Request a Feature links live).
- **Quit**: exit Checkpoint.

#### Main Window (Click "Open Checkpoint")

The main window has two tabs:

##### Settings Tab

- **Hotkey**: Change the global hotkey. Changes take effect immediately.
- **OBS Connection**: Configure the OBS WebSocket server hostname, port, and password. Changes take effect immediately and reconnect the client.
- **Categories**: View, add, and manage categories. New categories appear immediately in the hotkey popup.

##### Markers Tab

- **Filter**: Filter markers by recording file and/or category. Use the "All" option to see all markers.
- **Refresh**: Reload markers from the database based on the current filters.
- **Select All / Unselect All**: Quickly select or deselect all visible (filtered) markers.
- **Export to CSV**: Export the selected markers to a CSV file. A file dialog will appear to let you choose where to save the file.
- **Export to DaVinci Resolve (.edl)**: Export selected markers as an EDL file that can be imported into DaVinci Resolve. Select one or more markers and click the button to open an options dialog:
  - **FPS**: Choose the frame rate (24, 25, 30, 50, or 60) to match your Resolve timeline. Your last choice is remembered.
  - **Timeline start TC**: Specify the timeline's start timecode (default `01:00:00:00`). Markers are positioned relative to this timecode.
  - **Important**: The fps must match your Resolve timeline's frame rate, or markers will land proportionally off. Integer fps only (no 29.97 or 59.94 support); sources using fractional frame rates drift slightly (~3.6 s/hr).
  - One .edl file is created per recording file. Markers become Resolve markers at their begin timestamp with the duration spanning from begin to end; the description becomes the marker name, and the category determines the marker color.
  - To import in Resolve: right-click the timeline in the Media Pool → Timelines → Import → Timeline Markers from EDL, and select the .edl file.
- **Delete**: Remove selected markers after confirmation. You can also press **Del** to delete the current selection.

#### Clip Explorer (Click "Open Clip Explorer")

The Clip Explorer window allows you to review and adjust individual clips. Features:

- **Left pane**: Filter and sort controls
  - **Keyword**: Search for clips by keyword in the description (live filtering)
  - **Category**: Filter by category
  - **Min/Max duration**: Filter clips by duration range (in seconds; blank means no limit)
  - **Sort**: Reorder clips by Created (newest first), Duration (ascending or descending), or Category
  - **Marker list**: A scrollable table showing all matching markers with file name, begin/end timestamps, duration, description, and category

- **Right pane**: Details and boundary controls for the selected clip
  - **Description & Category**: Display the selected clip's metadata
  - **Begin/End timestamps**: Clickable labels to set the active boundary. Click to toggle which boundary (begin or end) is adjusted with arrow keys. The active boundary is highlighted in blue.
  - **Arrow keys**: Adjust the active boundary
    - **Left/Right arrow**: Move boundary ±5 seconds (default)
    - **Ctrl+Left/Right arrow**: Move boundary ±1 second (fine adjustment)
    - **Shift+Left/Right arrow**: Move boundary ±10 seconds (coarse adjustment)
  - **Video preview**: Embedded VLC player (if VLC is installed) showing the clip between begin and end timestamps, with looping playback. Click **Play** to toggle playback; the player automatically loops when reaching the end timestamp.
  - **Saved indicator**: A green "Saved" message appears briefly after each boundary adjustment, confirming the change was persisted to the database.

Each boundary adjustment is saved to the database immediately, so you can close and reopen the explorer without losing changes.

#### About Tab

The About tab displays:
- **Version**: The current Checkpoint version (dev builds show `0.0.0`; release builds derive the version from the git tag).
- **License**: GPL-3.0 license information and links.
- **Actions**:
  - **GitHub Repository**: Opens the project's GitHub page.
  - **Report a Bug**: Opens a pre-filled GitHub issue form with your Checkpoint version, OS, and Python version automatically included.
  - **Request a Feature**: Opens a pre-filled GitHub feature request form.
  - **Contribute**: Links to the contribution guide.
  - **Open Data Folder**: Opens `%APPDATA%\Checkpoint` so you can access `checkpoint.log` (useful when reporting bugs).
- **Acknowledgements**: Credits for the open-source libraries and tools that power Checkpoint.

### Configuration

Configuration is stored in `%APPDATA%\Checkpoint\config.json`. On first run, this file is created with defaults:

```json
{
  "obs_host": "localhost",
  "obs_port": 4455,
  "obs_password": "",
  "hotkey": "ctrl+f9",
  "last_duration_preset": "30s",
  "last_export_fps": 60
}
```

You can configure these settings via the Settings tab in the main window:
- **obs_host**: hostname or IP of the OBS WebSocket server (default: localhost)
- **obs_port**: port of the OBS WebSocket server (default: 4455)
- **obs_password**: WebSocket server password if set (default: empty)
- **hotkey**: global hotkey string (default: `ctrl+f9`; use syntax like `ctrl+f9`, `alt+shift+c`, etc.)
- **last_duration_preset**: the duration preset to use next time the hotkey popup appears (automatically updated)
- **last_export_fps**: the frame rate to use by default in the DaVinci Resolve EDL export dialog (automatically updated, default: 60)

Changes made in the Settings tab take effect immediately without restarting the app. You can also manage categories in the Settings tab; they are automatically suggested in the hotkey popup.

#### Optional: VLC for Video Preview

To enable video preview in the Clip Explorer, install VLC media player. If VLC is not installed, the Clip Explorer will show a message in the video frame but continue to work normally for boundary adjustment and metadata viewing. To install VLC:
- Download from https://www.videolan.org/vlc/
- Run the installer
- Restart Checkpoint

The app auto-detects VLC after installation. If you installed VLC after starting Checkpoint, restart the app.

### Data Storage

#### SQLite Database

All markers are stored in a single SQLite database at `%APPDATA%\Checkpoint\markers.db`. When you press the hotkey during a recording and confirm the popup, a row is inserted with the following information:

- **file_path**: Path to the recording file
- **timestamp_ms**: Timestamp in milliseconds since the recording started (the clip end)
- **timestamp_hms**: Timestamp formatted as HH:MM:SS.mmm (hours may exceed 23 for long recordings)
- **begin_timestamp_ms**: Timestamp in milliseconds where the clip begins (computed from end timestamp minus duration)
- **duration_hint_ms**: The duration preset (in milliseconds) that was selected in the hotkey popup
- **description**: Your description text
- **category**: Category (may be empty)
- **created_at**: Timestamp when the marker was created

You can view, filter, and export markers from the Markers tab in the main window. You can also adjust clip boundaries (begin and end timestamps) in the Clip Explorer and view video previews.

#### Marker Export

You can export selected markers to CSV from the Markers tab. The exported CSV uses the same schema as above (file_path, timestamp_ms, timestamp_hms, description, category) and can be imported into other tools or analysis pipelines.

#### Known Categories

Previously used categories are stored in `%APPDATA%\Checkpoint\categories.json`. This file is created automatically and updated whenever you enter a new category in the popup or via the Settings tab.

### Versioning and Releases

**Development builds** report version `0.0.0`. This is the default value in the source code.

**Release builds** derive the version from the git tag at release time. When you create a git tag like `v1.0.0`, the automated release workflow:
1. Checks out the tagged commit
2. Rewrites the `__version__` string in `src/checkpoint/__init__.py` to `1.0.0` (stripping the `v` prefix)
3. Builds the Windows exe via PyInstaller
4. Uploads the exe to the GitHub release

The exe will report the corresponding version in the About tab and in bug/feature reports. You can also see the version by running `python -c "import checkpoint; print(checkpoint.__version__)"` (or just check the About tab in the app).
