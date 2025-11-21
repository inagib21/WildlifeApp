#!/usr/bin/env python3
"""Test webhook endpoint with a sample detection"""

import requests
import json
from datetime import datetime

# Test webhook endpoint
webhook_url = "http://localhost:8001/api/motioneye/webhook"

# Create a test webhook payload
test_payload = {
    "camera_id": 6,
    "file_path": "/var/lib/motioneye/Camera6/2025-11-03/test-image.jpg",
    "timestamp": datetime.now().isoformat(),
    "type": "picture_save"
}

print(f"Testing webhook endpoint: {webhook_url}")
print(f"Payload: {json.dumps(test_payload, indent=2)}")

try:
    response = requests.post(webhook_url, json=test_payload, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"\nError: {e}")

