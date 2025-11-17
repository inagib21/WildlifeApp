import logging
import os
from typing import Iterable


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_access_logs(env_names: Iterable[str] = ("DISABLE_UVICORN_ACCESS_LOGS",)) -> bool:
    disable = any(
        _truthy(os.getenv(name, "0"))
        for name in env_names
    )
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.disabled = disable
    return disable

