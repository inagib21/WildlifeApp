import pytest
from starlette.requests import Request

from backend.motioneye_webhook import parse_motioneye_payload


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _build_request(body: bytes, content_type: str = "application/json") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/motioneye/webhook",
        "headers": [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
        ],
        "query_string": b"",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.mark.anyio
async def test_parse_motioneye_payload_from_json():
    body = (
        b'{"camera_id": "12", "file_path": "/var/lib/motioneye/Camera12/test.jpg", '
        b'"type": "picture_save", "timestamp": "2025-11-13T12:00:00Z"}'
    )
    request = _build_request(body, "application/json")

    payload = await parse_motioneye_payload(request)

    assert payload["camera_id"] == 12
    assert payload["file_path"] == "/var/lib/motioneye/Camera12/test.jpg"
    assert payload["event_type"] == "picture_save"
    assert payload["timestamp"] == "2025-11-13T12:00:00Z"


@pytest.mark.anyio
async def test_parse_motioneye_payload_from_form_urlencoded():
    body = (
        "camera=7&file=/var/lib/motioneye/Camera7/2025-11-13/12-00-00.jpg"
        "&event=picture_save&when=2025-11-13T12:00:00Z"
    ).encode()
    request = _build_request(body, "application/x-www-form-urlencoded")

    payload = await parse_motioneye_payload(request)

    assert payload["camera_id"] == 7
    assert payload["file_path"] == "/var/lib/motioneye/Camera7/2025-11-13/12-00-00.jpg"
    assert payload["event_type"] == "picture_save"
    assert payload["timestamp"] == "2025-11-13T12:00:00Z"

