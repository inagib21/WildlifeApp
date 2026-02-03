#!/usr/bin/env python3
"""Script to check what the API endpoints actually return"""
import sys
import os
import requests
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_api_responses():
    """Check what the API endpoints return"""
    base_url = "http://localhost:8001"
    
    print("=" * 60)
    print("API Response Check")
    print("=" * 60)
    print()
    
    # Check cameras endpoint
    try:
        print("[1] Checking /cameras endpoint...")
        response = requests.get(f"{base_url}/cameras", timeout=5)
        if response.status_code == 200:
            cameras = response.json()
            print(f"   Status: OK")
            print(f"   Total cameras returned: {len(cameras)}")
            active = [c for c in cameras if c.get("is_active", True)]
            print(f"   Active cameras: {len(active)}")
            print(f"   Inactive cameras: {len(cameras) - len(active)}")
            print()
            print("   Camera details:")
            for cam in cameras:
                print(f"     ID {cam.get('id')}: {cam.get('name')} - Active: {cam.get('is_active')}")
        else:
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Check detections endpoint
    try:
        print("[2] Checking /detections endpoint...")
        response = requests.get(f"{base_url}/detections?limit=10", timeout=5)
        if response.status_code == 200:
            detections = response.json()
            print(f"   Status: OK")
            print(f"   Total detections returned: {len(detections)}")
            if len(detections) > 0:
                print(f"   Sample detection: ID {detections[0].get('id')}, Camera {detections[0].get('camera_id')}, Species: {detections[0].get('species')}")
            else:
                print("   WARNING: No detections returned!")
        else:
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()
    
    # Check detections count
    try:
        print("[3] Checking /detections/count endpoint...")
        response = requests.get(f"{base_url}/detections/count", timeout=5)
        if response.status_code == 200:
            count_data = response.json()
            count = count_data.get("count") if isinstance(count_data, dict) else count_data
            print(f"   Status: OK")
            print(f"   Total detections in database: {count}")
        else:
            print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"   ERROR: {e}")
    print()

if __name__ == "__main__":
    check_api_responses()
