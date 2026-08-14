from __future__ import annotations

from urllib.parse import SplitResult, urlsplit


OVERLAY_EXCLUDED_PATH_SEGMENTS = frozenset(
    {"watch", "shorts", "live", "embed", "v", "clip", "channel", "c", "user"}
)


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


def should_show_overlay(raw_url: str | None) -> bool:
    """Return whether a URL is a YouTube page that should be covered."""
    parsed = parse_browser_url(raw_url)
    if parsed is None:
        return False

    host = parsed.hostname.rstrip(".").lower()
    if host == "youtu.be" or host.endswith(".youtu.be"):
        return False
    if host != "youtube.com" and not host.endswith(".youtube.com"):
        return False

    first_segment = parsed.path.lstrip("/").split("/", 1)[0].lower()
    if first_segment.startswith("@"):
        return False
    return first_segment not in OVERLAY_EXCLUDED_PATH_SEGMENTS
