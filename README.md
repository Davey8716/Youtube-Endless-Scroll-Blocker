# YouTube Endless Scroll Blocker

A small Windows tray app that places click-blocking overlays over YouTube's most distracting areas in Brave. It blocks home and discovery feeds, watch-page recommendations, and comments after you scroll past the video, while leaving search, playlists, and channel pages available.

> [!IMPORTANT]
> The overlay positions are designed for a maximized Brave window on a 1920 x 1080 landscape display. Watch-page suggestions are also supported on a 1080 x 1920 portrait display; home/discovery feeds and comments are not yet blocked in portrait. Other resolutions, browser layouts, display scaling settings, and browsers are not supported.

## What it blocks

| Page or state | Result |
| --- | --- |
| YouTube home and other non-video feeds | The main recommendations area is covered and cannot be clicked. |
| A regular watch page | The recommendations sidebar is covered. |
| A watch page in Theatre mode | The recommendations sidebar overlay is hidden so the enlarged player remains unobstructed. |
| A watch page after the player is scrolled out of view | The comments area is covered as well. Scrolling up reveals the player again and removes the comments overlay. |
| Search results, channel pages, playlists, and the **You** section | No overlay, so navigation and intentional viewing remain available. |
| YouTube Studio video tools | No overlay. |
| Fullscreen video, minimized Brave, or a non-maximized Brave window | No overlay. |

The app follows every eligible maximized Brave window. Each overlay stays attached to its corresponding browser window, so focusing another Brave window does not remove blockers elsewhere and other applications can still appear above them normally.

## Requirements

- Windows
- [Brave](https://brave.com/) browser
- A 1920 x 1080 landscape display, or a 1080 x 1920 portrait display for watch-page suggestions, with Brave maximized
- Python 3.10 when running from source

## Run from source

Clone the repository, open PowerShell in the project directory, and run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

The app starts enabled and appears in the Windows system tray. Only one instance can run at a time.

## Tray controls

- **Start with Windows** registers or removes the app for the current Windows user. It is off by default.
- **Turn Off / Turn On** temporarily disables or enables every blocker for the current session.
- **Pause** disables every blocker for the selected number of minutes or hours, then turns blocking back on automatically. While active, the tray entry shows the selected pause duration; selecting **Turn On** resumes blocking early.
- **Block home and discovery feeds** controls YouTube's non-video recommendation feeds.
- **Block watch-page suggestions** controls the recommendations sidebar beside a video.
- **Block comments** controls the comments overlay that appears after the video player has been scrolled out of view.
- **Exit** closes the app.

The recommendation and comment choices are saved in:

```text
%LOCALAPPDATA%\YouTube Endless Scroll Blocker\settings.json
```

The **Start with Windows** preference is saved in the same file and uses the current user's standard Windows Run entry. Scheduled tasks created by the user are not changed.

The master Turn Off / Turn On control and timed pauses are session-only and do not change those saved choices. Closing the app discards an active pause.

All tray controls and saved blocker preferences apply globally to every Brave window and tab.

## Development

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the test suite:

```powershell
pytest
```

## Build the executable

Regenerate the icon if `tools/generate_icon.py` has changed, then build with PyInstaller:

```powershell
python tools/generate_icon.py
pyinstaller --clean --noconfirm YouTubeEndlessScrollBlocker.spec
```

The executable is written to `dist\YouTubeEndlessScrollBlocker.exe`.

## How it works

The app reads the active Brave address bar through Windows UI Automation and creates native black overlay windows in the relevant screen regions. It does not inject code into YouTube or install a browser extension. Mouse-wheel input is forwarded to Brave so you can still scroll back to an allowed part of the page.
