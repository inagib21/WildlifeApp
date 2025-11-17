import json
import inspect
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from fastapi import Request


async def _read_json_body(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}
    return {}


async def _read_form_body(request: Request) -> Dict[str, Any]:
    try:
        form = await request.form()
        if form:
            return dict(form)
    except Exception:
        return {}
    return {}


async def _read_raw_body(request: Request) -> Dict[str, Any]:
    try:
        body = await request.body()
        if not body:
            return {}
        parsed = parse_qs(body.decode(errors="ignore"))
        return {key: values[-1] if values else "" for key, values in parsed.items()}
    except Exception:
        return {}


def _coerce_int(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _first_present(container: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if key in container and container[key] not in (None, ""):
            return container[key]
    return None


def _read_query_params(request: Request) -> Dict[str, Any]:
    try:
        return dict(request.query_params)
    except Exception:
        return {}


async def parse_motioneye_payload(request: Request) -> Dict[str, Any]:
    """
    Parse payloads sent by MotionEye webhooks.

    MotionEye can send JSON, form-urlencoded, or query-string payloads depending on configuration.
    This helper normalises the data into a consistent dict.
    """
    data: Dict[str, Any] = {}

    parsers = (
        _read_json_body,
        _read_form_body,
        _read_raw_body,
        _read_query_params,
    )

    for parser in parsers:
        if inspect.iscoroutinefunction(parser):
            chunk = await parser(request)
        else:
            chunk = parser(request)
        if chunk:
            data.update(chunk)

    camera_id = _coerce_int(
        _first_present(data, "camera_id", "camera", "id", "cameraid")
    )
    file_path = _first_present(
        data, "file_path", "file", "path", "filename", "full_path"
    )
    event_type = _first_present(data, "type", "event", "event_type", "action") or "unknown"
    timestamp = _first_present(data, "timestamp", "time", "when", "ts")

    return {
        "camera_id": camera_id,
        "file_path": file_path,
        "event_type": event_type,
        "timestamp": timestamp,
        "raw": data,
    }

