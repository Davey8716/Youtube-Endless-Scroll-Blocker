import pytest

from youtube_scroll_blocker.url_rules import OverlayMode, overlay_mode_for_url, parse_browser_url, should_show_overlay


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/",
        "youtube.com",
        "www.youtube.com/feed/subscriptions",
        "https://www.youtube.com/results?search_query=python",
        "https://music.youtube.com/explore",
    ],
)
def test_non_video_youtube_urls_show_overlay(url: str) -> None:
    assert should_show_overlay(url)


@pytest.mark.parametrize("route", ["watch", "shorts/id", "live/id", "embed/id", "v/id", "clip/id"])
def test_video_routes_do_not_show_overlay(route: str) -> None:
    assert not should_show_overlay(f"https://www.youtube.com/{route}?feature=test")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=suwW4PFgD54",
        "www.youtube.com/WATCH?v=suwW4PFgD54&feature=share",
        "https://m.youtube.com/watch?feature=test&v=video-id",
    ],
)
def test_valid_watch_urls_use_watch_overlay(url: str) -> None:
    assert overlay_mode_for_url(url) is OverlayMode.WATCH
    assert not should_show_overlay(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?feature=share",
        "https://www.youtube.com/watch?v=",
    ],
)
def test_watch_route_without_video_id_has_no_overlay(url: str) -> None:
    assert overlay_mode_for_url(url) is OverlayMode.NONE


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/shorts/suwW4PFgD54",
        "www.youtube.com/SHORTS/suwW4PFgD54?feature=share",
    ],
)
def test_shorts_pages_remain_exempt(url: str) -> None:
    assert overlay_mode_for_url(url) is OverlayMode.NONE


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/@MandyCaneLane",
        "https://www.youtube.com/@MandyCaneLane/search?query=recipe",
        "https://www.youtube.com/@MandyCaneLane/videos",
        "http://m.youtube.com/@example/videos",
        "https://www.youtube.com/channel/UC123/search?query=test",
        "https://www.youtube.com/c/example",
        "https://www.youtube.com/user/example",
    ],
)
def test_channel_pages_do_not_show_overlay(url: str) -> None:
    assert not should_show_overlay(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/feed/you",
        "https://www.youtube.com/feed/history",
        "https://www.youtube.com/feed/playlists",
        "https://www.youtube.com/feed/downloads",
        "https://www.youtube.com/feed/courses",
        "https://www.youtube.com/feed/library",
        "https://www.youtube.com/FEED/HISTORY/?query=ignored",
    ],
)
def test_you_section_feed_pages_do_not_show_overlay(url: str) -> None:
    assert not should_show_overlay(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=WL",
        "https://www.youtube.com/playlist?list=LL",
        "https://www.youtube.com/playlist?list=PL123&playnext=1",
        "www.youtube.com/PLAYLIST?list=custom",
    ],
)
def test_all_playlist_pages_do_not_show_overlay(url: str) -> None:
    assert not should_show_overlay(url)


def test_your_videos_studio_page_does_not_show_overlay() -> None:
    assert not should_show_overlay("https://studio.youtube.com/channel/UC123/videos")


@pytest.mark.parametrize(
    "url",
    [
        "https://studio.youtube.com/video/VIDEO123/edit",
        "https://studio.youtube.com/video/VIDEO123/analytics/tab-overview/period-default",
        "https://studio.youtube.com/video/VIDEO123/editor",
        "https://studio.youtube.com/video/VIDEO123/comments/inbox",
        "https://studio.youtube.com/video/VIDEO123/translations",
        "https://studio.youtube.com/video/VIDEO123/copyright",
        "https://studio.youtube.com/video/VIDEO123/clips",
    ],
)
def test_studio_video_content_pages_do_not_show_overlay(url: str) -> None:
    assert not should_show_overlay(url)


def test_video_path_exemption_is_scoped_to_studio_host() -> None:
    assert should_show_overlay("https://www.youtube.com/video/VIDEO123/edit")


def test_similarly_named_non_channel_route_still_shows_overlay() -> None:
    assert should_show_overlay("https://www.youtube.com/channels")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/feed/subscriptions",
        "https://www.youtube.com/results?search_query=python",
        "https://www.youtube.com/feed/history-other",
        "https://www.youtube.com/feed/history/extra",
        "https://www.youtube.com/playlists",
    ],
)
def test_non_you_section_routes_remain_blocked(url: str) -> None:
    assert should_show_overlay(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/suwW4PFgD54",
        "youtu.be/suwW4PFgD54",
        "https://youtube.com.evil.example/",
        "https://notyoutube.com/",
        "file:///youtube.com/",
        "not a url",
        "",
        None,
    ],
)
def test_non_matching_or_malformed_urls_do_not_show_overlay(url: str | None) -> None:
    assert not should_show_overlay(url)


def test_video_route_matching_is_case_insensitive() -> None:
    assert not should_show_overlay("HTTPS://WWW.YOUTUBE.COM/WATCH?v=suwW4PFgD54")


def test_parser_adds_missing_scheme() -> None:
    parsed = parse_browser_url("www.youtube.com/results?search_query=test")
    assert parsed is not None
    assert parsed.scheme == "https"
    assert parsed.hostname == "www.youtube.com"
