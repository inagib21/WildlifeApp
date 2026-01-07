#!/usr/bin/env python3
"""Diagnostic script to check why detections aren't appearing"""
from database import SessionLocal, Detection, Camera
from datetime import datetime, timedelta
import os
import sys

db = SessionLocal()

print("=" * 70)
print("DETECTION SYSTEM DIAGNOSTIC")
print("=" * 70)

# 1. Check recent detections
now = datetime.now()
last_hour = db.query(Detection).filter(Detection.timestamp > now - timedelta(hours=1)).count()
last_24h = db.query(Detection).filter(Detection.timestamp > now - timedelta(hours=24)).count()
last_detection = db.query(Detection).order_by(Detection.timestamp.desc()).first()

print(f"\n📊 Detection Statistics:")
print(f"   Last hour: {last_hour}")
print(f"   Last 24 hours: {last_24h}")
if last_detection:
    hours_ago = (now - last_detection.timestamp).total_seconds() / 3600
    print(f"   Last detection: {hours_ago:.1f} hours ago")
    print(f"     Camera ID: {last_detection.camera_id}, Species: {last_detection.species}")
else:
    print(f"   ⚠️  No detections found in database")

# 2. Check cameras
print(f"\n📹 Camera Status:")
cameras = db.query(Camera).all()
active_cameras = [c for c in cameras if c.is_active and c.detection_enabled]
print(f"   Total cameras: {len(cameras)}")
print(f"   Active with detection: {len(active_cameras)}")
for c in cameras:
    status = "✓" if c.is_active and c.detection_enabled else "✗"
    print(f"   {status} Camera {c.id}: {c.name} (Active: {c.is_active}, Detection: {c.detection_enabled})")

# 3. Check media directory
print(f"\n📁 Media Directory Check:")
wildlife_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
media_path = os.path.join(wildlife_app_dir, "motioneye_media")
if os.path.exists(media_path):
    print(f"   ✓ Found: {media_path}")
    
    # Count recent files
    recent_files = []
    for root, dirs, files in os.walk(media_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(file_path)
                    hours_old = (now.timestamp() - mtime) / 3600
                    if hours_old < 24:
                        recent_files.append((file_path, hours_old))
                except:
                    pass
    
    print(f"   Recent image files (24h): {len(recent_files)}")
    if recent_files:
        print(f"   Most recent: {recent_files[0][1]:.1f} hours ago")
        print(f"     Path: {recent_files[0][0]}")
else:
    print(f"   ✗ Not found: {media_path}")

# 4. Check webhook configuration
print(f"\n🔗 Webhook Configuration:")
print(f"   Expected URL: http://host.docker.internal:8001/api/motioneye/webhook")
print(f"   (MotionEye in Docker needs 'host.docker.internal' not 'localhost')")

# Check config files
config_dir = os.path.join(wildlife_app_dir, "motioneye_config")
if os.path.exists(config_dir):
    config_files = [f for f in os.listdir(config_dir) if f.startswith("camera-") and f.endswith(".conf")]
    print(f"   Camera config files: {len(config_files)}")
    
    # Check a sample config
    if config_files:
        sample_config = os.path.join(config_dir, config_files[0])
        with open(sample_config, 'r') as f:
            content = f.read()
            if "host.docker.internal:8001" in content:
                print(f"   ✓ Webhook URL is correct in configs")
            elif "localhost:8001" in content:
                print(f"   ✗ Webhook URL still uses 'localhost' - needs restart")
            else:
                print(f"   ⚠️  Webhook URL not found in config")

# 5. Recommendations
print(f"\n💡 Recommendations:")
if last_24h == 0:
    print(f"   1. ⚠️  No detections in 24h - check if MotionEye is capturing images")
    print(f"   2. Restart MotionEye: docker-compose restart motioneye")
    print(f"   3. Check backend logs for 'MotionEye webhook received' messages")
    print(f"   4. Verify MotionEye is saving pictures (picture_output = on)")
    print(f"   5. Test webhook manually from MotionEye container")
elif len(recent_files) > 0 and last_24h == 0:
    print(f"   1. ⚠️  Images are being captured but not processed")
    print(f"   2. Webhooks may not be reaching backend")
    print(f"   3. Check backend logs for webhook errors")
    print(f"   4. Verify webhook URL in MotionEye configs")
    print(f"   5. Restart MotionEye after config changes")
else:
    print(f"   ✓ System appears to be working")

print("\n" + "=" * 70)
print("Next Steps:")
print("=" * 70)
print("1. Check backend console/logs for webhook messages")
print("2. Restart MotionEye: docker-compose restart motioneye")
print("3. Wait 5-10 minutes for new motion events")
print("4. Check this script again to see if detections appear")

db.close()

