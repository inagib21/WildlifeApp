import logging

import pytest


@pytest.fixture(autouse=True)
def reset_access_logger():
    logger = logging.getLogger("uvicorn.access")
    previous = logger.disabled
    try:
        yield
    finally:
        logger.disabled = previous


def test_configure_access_logs_disables(monkeypatch):
    monkeypatch.setenv("DISABLE_UVICORN_ACCESS_LOGS", "1")
    from backend.logging_utils import configure_access_logs

    configure_access_logs()

    assert logging.getLogger("uvicorn.access").disabled is True


def test_configure_access_logs_enables(monkeypatch):
    monkeypatch.delenv("DISABLE_UVICORN_ACCESS_LOGS", raising=False)
    from backend.logging_utils import configure_access_logs

    configure_access_logs()

    assert logging.getLogger("uvicorn.access").disabled is False

