import time

from backend.motioneye_events import should_process_event, _reset_event_cache


def test_should_process_event_allows_first_occurrence():
    _reset_event_cache()
    assert should_process_event("/var/lib/motioneye/Camera1/file.jpg", now=0.0) is True


def test_should_process_event_blocks_immediate_duplicate():
    _reset_event_cache()
    path = "/var/lib/motioneye/Camera1/file.jpg"
    assert should_process_event(path, now=1.0) is True
    assert should_process_event(path, now=2.0) is False


def test_should_process_event_allows_after_ttl():
    _reset_event_cache()
    path = "/var/lib/motioneye/Camera1/file.jpg"
    assert should_process_event(path, now=1.0, ttl=5.0) is True
    assert should_process_event(path, now=2.0, ttl=5.0) is False
    assert should_process_event(path, now=7.0, ttl=5.0) is True

