# YouTube Endless Scroll Blocker

A Windows tray application that covers non-video YouTube pages in a maximized Brave window. Video playback pages remain unobstructed.

## Behavior

- Starts enabled and remains in the Windows system tray.
- Shows a click-blocking black rectangle at `(260, 171)` with size `1631 x 852`, relative to the active Brave monitor.
- Shows the overlay on non-video `youtube.com` pages.
- Hides the overlay on video routes such as `/watch`, `/shorts`, `/live`, `/embed`, `/v`, and `/clip`.
- Hides the overlay on handle and channel pages so their search and navigation controls remain usable.
- Hides the overlay on every destination in YouTube's **You** section, including History, Playlists, Watch later, Liked videos, Your videos, Downloads, and Courses.
- Hides the overlay throughout YouTube Studio's per-video content tools, including Details, Analytics, Editor, Comments, Subtitles, Claims, and Clips.
- Provides `Turn Off` / `Turn On` and `Exit` tray-menu actions.
- Silently exits a second launch while one instance is already running.

## Development

Python 3.10 and Windows are required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python main.py
```

Run the automated tests:

```powershell
pytest
```

## Release build

Regenerate the icon after editing the icon source script, then build the single-file, windowed executable:

```powershell
python tools/generate_icon.py
pyinstaller --clean --noconfirm YouTubeEndlessScrollBlocker.spec
```

The executable is written to `dist\YouTubeEndlessScrollBlocker.exe`.
