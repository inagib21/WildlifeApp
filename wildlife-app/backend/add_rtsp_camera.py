#!/usr/bin/env python3
"""Script to add RTSP camera to MotionEye via web interface instructions"""

import sys
import webbrowser

print("=" * 60)
print("Add RTSP Camera to MotionEye")
print("=" * 60)
print()
print("Camera Details:")
print(f"  URL: rtsp://192.168.88.171:554")
print(f"  Name: RTSP Camera 192.168.88.171")
print()
print("Since MotionEye requires authentication, please add it manually:")
print()
print("1. Open MotionEye: http://localhost:8765")
print("2. Click '+' or 'Add Camera' button")
print("3. Select 'Network Camera'")
print("4. Enter:")
print("   - Network Camera URL: rtsp://192.168.88.171:554")
print("   - Camera Name: RTSP Camera 192.168.88.171")
print("   - Width: 640")
print("   - Height: 480")
print("   - Frame Rate: 30")
print("5. Click 'Save'")
print()
print("After adding, sync cameras in Wildlife app:")
print("  http://localhost:3000/cameras -> Click 'Sync Cameras'")
print()
print("Opening MotionEye in your browser...")
print()
webbrowser.open("http://localhost:8765")
