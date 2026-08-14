import pytest

from youtube_scroll_blocker.url_rules import parse_browser_url, should_show_overlay


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


def test_similarly_named_non_channel_route_still_shows_overlay() -> None:
    assert should_show_overlay("https://www.youtube.com/channels")


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
