
import requests
import json
import time

# URL of the running backend
URL = "http://localhost:8001/api/motioneye/webhook"

# Payload simulating a MotionEye webhook
# It expects multipart/form-data usually, or JSON?
# Let's check parse_motioneye_payload implementation to be sure, but standard MotionEye webhooks are often POST requests with parameters.
# However, the previous log showed "POST /api/motioneye/webhook HTTP/1.1" 200 OK.
# Wait, the log showed 200 OK!
# But the audit log insert ERROR happened.
# This means the request SUCCEEDED from the client's perspective (because of the `try ... except` block in the router/handler that catches exception and returns error JSON?), OR it returned 200 OK despite the internal failure?
# The handler returns `{"status": "error"}` in the except block.
# So I should see the return value.

def test_webhook():
    print(f"Testing webhook at {URL}")
    
    # Simulating a payload. Usually MotionEye sends POST data.
    # The handler calls `parse_motioneye_payload`.
    # Let's try sending a JSON payload first.
    payload = {
        "camera_id": 2,
        "file_path": "/var/lib/motioneye/test_bug.jpg",
        "timestamp": int(time.time()),
        "event_type": "motion"
    }

    try:
        response = requests.post(URL, json=payload, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_webhook()
