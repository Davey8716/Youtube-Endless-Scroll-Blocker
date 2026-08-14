from uuid import uuid4

from youtube_scroll_blocker.mutex import SingleInstanceMutex


def test_named_mutex_allows_only_one_owner() -> None:
    name = rf"Local\YouTubeEndlessScrollBlocker.Test.{uuid4()}"
    first = SingleInstanceMutex(name)
    second = SingleInstanceMutex(name)
    try:
        assert first.acquired
        assert not second.acquired
    finally:
        second.close()
        first.close()

    third = SingleInstanceMutex(name)
    try:
        assert third.acquired
    finally:
        third.close()
