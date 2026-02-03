"""Diagnostic script to check why detections stopped"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Detection, Camera
from services.motioneye import MotionEyeClient
from config import MOTIONEYE_URL
from routers.settings import get_setting

def check_detections():
    """Check recent detections"""
    db = SessionLocal()
    try:
        # Get most recent detection
        recent = db.query(Detection).order_by(Detection.timestamp.desc()).first()
        if recent:
            print(f"[OK] Most recent detection:")
            print(f"   ID: {recent.id}")
            print(f"   Species: {recent.species}")
            print(f"   Timestamp: {recent.timestamp}")
            print(f"   Camera ID: {recent.camera_id}")
            days_ago = (datetime.utcnow() - recent.timestamp).days
            print(f"   Days ago: {days_ago}")
        else:
            print("[ERROR] No detections found in database")
        
        # Count detections in last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        count_week = db.query(Detection).filter(Detection.timestamp >= week_ago).count()
        print(f"\n[INFO] Detections in last 7 days: {count_week}")
        
        # Count total detections
        total = db.query(Detection).count()
        print(f"[INFO] Total detections: {total}")
        
    finally:
        db.close()

def check_ai_status():
    """Check if AI processing is enabled"""
    db = SessionLocal()
    try:
        ai_enabled = get_setting(db, "ai_enabled", default=True)
        status = "[OK] Enabled" if ai_enabled else "[ERROR] Disabled"
        print(f"\n[AI] AI Processing: {status}")
    finally:
        db.close()

def check_motioneye():
    """Check MotionEye connectivity and webhook configuration"""
    print(f"\n[MOTIONEYE] MotionEye Check:")
    print(f"   URL: {MOTIONEYE_URL}")
    
    try:
        client = MotionEyeClient()
        cameras = client.get_cameras()
        if cameras:
            print(f"   [OK] MotionEye accessible - {len(cameras)} cameras found")
            
            # Check webhook configuration for each camera
            print(f"\n   Webhook Configuration:")
            for cam in cameras[:5]:  # Check first 5 cameras
                cam_id = cam.get("id")
                if cam_id:
                    config = client.get_camera_config(cam_id)
                    on_picture_save = config.get("on_picture_save", "")
                    on_movie_end = config.get("on_movie_end", "")
                    
                    has_webhook = "webhook" in on_picture_save.lower() or "webhook" in on_movie_end.lower()
                    webhook_ok = "localhost:8001" in on_picture_save or "localhost:8001" in on_movie_end
                    
                    status = "[OK]" if (has_webhook and webhook_ok) else "[ERROR]"
                    print(f"   {status} Camera {cam_id} ({cam.get('name', 'Unknown')}):")
                    if has_webhook:
                        if webhook_ok:
                            print(f"      Webhook configured correctly")
                        else:
                            print(f"      [WARN] Webhook exists but may not point to backend")
                    else:
                        print(f"      [ERROR] No webhook configured")
        else:
            print(f"   [WARN] No cameras found in MotionEye")
    except Exception as e:
        print(f"   [ERROR] MotionEye not accessible: {e}")

def check_cameras():
    """Check camera status"""
    db = SessionLocal()
    try:
        cameras = db.query(Camera).filter(Camera.is_active == True).all()
        print(f"\n[CAMERAS] Active Cameras: {len(cameras)}")
        for cam in cameras:
            print(f"   - Camera {cam.id}: {cam.name} (Active: {cam.is_active})")
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Detection System Diagnostic")
    print("=" * 60)
    
    check_detections()
    check_ai_status()
    check_cameras()
    check_motioneye()
    
    print("\n" + "=" * 60)
    print("Recommendations:")
    print("=" * 60)
    print("1. Verify MotionEye is running and accessible")
    print("2. Check that webhooks are configured in MotionEye:")
    print("   - Go to MotionEye web interface")
    print("   - For each camera, check 'on_picture_save' or 'on_movie_end'")
    print("   - Should contain: http://localhost:8001/api/motioneye/webhook")
    print("3. Verify motion detection is enabled for cameras")
    print("4. Check backend logs for webhook errors")
    print("5. Test webhook manually by triggering motion detection")
    print("=" * 60)
