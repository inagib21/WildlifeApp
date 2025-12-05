#!/usr/bin/env python3
"""Test if MotionEye can reach the backend webhook endpoint"""
import requests
import sys

print("=" * 70)
print("WEBHOOK CONNECTIVITY TEST")
print("=" * 70)

# Test from host
print("\n1. Testing from host machine...")
try:
    response = requests.get("http://localhost:8001/health", timeout=5)
    print(f"   ✓ Backend is accessible from host: {response.status_code}")
except Exception as e:
    print(f"   ✗ Backend not accessible: {e}")
    sys.exit(1)

# Test webhook endpoint
print("\n2. Testing webhook endpoint from host...")
test_payload = {
    "camera_id": 1,
    "file_path": "/var/lib/motioneye/Camera1/2025-12-05/test.jpg",
    "type": "picture_save"
}
try:
    response = requests.post(
        "http://localhost:8001/api/motioneye/webhook",
        json=test_payload,
        timeout=5
    )
    print(f"   ✓ Webhook endpoint responds: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
except Exception as e:
    print(f"   ✗ Webhook endpoint failed: {e}")
    sys.exit(1)

# Instructions
print("\n" + "=" * 70)
print("NEXT STEPS:")
print("=" * 70)
print("1. MotionEye needs to be restarted to load new webhook configs")
print("2. Run: cd wildlife-app && docker-compose restart motioneye")
print("3. Wait 5-10 minutes for new motion events")
print("4. Check backend logs for 'MotionEye webhook received' messages")
print("5. If still not working, MotionEye may not be able to reach")
print("   host.docker.internal - check Docker network settings")

