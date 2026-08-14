from __future__ import annotations

from enum import Enum, auto
from urllib.parse import SplitResult, parse_qs, urlsplit


OVERLAY_EXCLUDED_PATH_SEGMENTS = frozenset(
    {"watch", "shorts", "live", "embed", "v", "clip", "channel", "c", "user", "playlist"}
)
YOU_SECTION_FEED_ROUTES = frozenset(
    {
        ("feed", "you"),
        ("feed", "history"),
        ("feed", "playlists"),
        ("feed", "downloads"),
        ("feed", "courses"),
        ("feed", "library"),
    }
)


class OverlayMode(Enum):
    NONE = auto()
    STANDARD = auto()
    WATCH = auto()


def parse_browser_url(raw_url: str | None) -> SplitResult | None:
    """Parse an address-bar value, accepting Chromium's scheme-less display form."""
    if not raw_url:
        return None

    value = raw_url.strip()
    if not value or any(character.isspace() for character in value):
        return None

    if "://" not in value:
        value = f"https://{value}"

    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except (TypeError, ValueError):
        return None

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    return parsed


def overlay_mode_for_url(raw_url: str | None) -> OverlayMode:
    """Classify which overlay, if any, applies to an address-bar URL."""
    parsed = parse_browser_url(raw_url)
    if parsed is None:
        return OverlayMode.NONE

    host = parsed.hostname.rstrip(".").lower()
    if host == "youtu.be" or host.endswith(".youtu.be"):
        return OverlayMode.NONE
    if host != "youtube.com" and not host.endswith(".youtube.com"):
        return OverlayMode.NONE

    normalized_path = parsed.path.strip("/").lower()
    path_segments = tuple(normalized_path.split("/")) if normalized_path else ()
    if path_segments in YOU_SECTION_FEED_ROUTES:
        return OverlayMode.NONE

    first_segment = path_segments[0] if path_segments else ""
    if first_segment == "watch":
        video_ids = parse_qs(parsed.query).get("v", [])
        return OverlayMode.WATCH if any(video_id.strip() for video_id in video_ids) else OverlayMode.NONE
    if host == "studio.youtube.com" and first_segment == "video":
        return OverlayMode.NONE
    if first_segment.startswith("@"):
        return OverlayMode.NONE
    if first_segment in OVERLAY_EXCLUDED_PATH_SEGMENTS:
        return OverlayMode.NONE
    return OverlayMode.STANDARD


def should_show_overlay(raw_url: str | None) -> bool:
    """Return whether the original standard overlay applies to a URL."""
    return overlay_mode_for_url(raw_url) is OverlayMode.STANDARD
