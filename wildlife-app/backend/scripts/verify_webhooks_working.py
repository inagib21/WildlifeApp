"""Script to verify webhooks are working by checking recent detections"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Detection

def check_recent_detections():
    """Check for recent detections to verify webhooks are working"""
    print("=" * 60)
    print("Webhook Verification - Recent Detections Check")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Check detections in last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = db.query(Detection).filter(Detection.timestamp >= hour_ago).count()
        
        # Check detections in last 24 hours
        day_ago = datetime.utcnow() - timedelta(days=1)
        day_count = db.query(Detection).filter(Detection.timestamp >= day_ago).count()
        
        # Get most recent detection
        most_recent = db.query(Detection).order_by(Detection.timestamp.desc()).first()
        
        print(f"\nDetections in last hour: {recent_count}")
        print(f"Detections in last 24 hours: {day_count}")
        
        if most_recent:
            time_diff = datetime.utcnow() - most_recent.timestamp
            hours_ago = time_diff.total_seconds() / 3600
            
            print(f"\nMost recent detection:")
            print(f"  ID: {most_recent.id}")
            print(f"  Species: {most_recent.species}")
            print(f"  Camera ID: {most_recent.camera_id}")
            print(f"  Timestamp: {most_recent.timestamp}")
            print(f"  Time ago: {hours_ago:.1f} hours")
            
            if hours_ago < 1:
                print("\n[OK] Webhooks appear to be working! Recent detections found.")
            elif hours_ago < 24:
                print("\n[WARN] Last detection was several hours ago.")
                print("       Webhooks may be working but no recent motion detected.")
            else:
                print(f"\n[ERROR] No detections in the last {hours_ago:.1f} hours.")
                print("        Webhooks may not be configured or working.")
        else:
            print("\n[ERROR] No detections found in database at all.")
            print("        Webhooks are definitely not working.")
        
        print("\n" + "=" * 60)
        print("Recommendations:")
        print("=" * 60)
        
        if recent_count == 0:
            print("1. Verify webhooks are configured in MotionEye")
            print("2. Trigger motion detection on a camera to test")
            print("3. Check backend logs for webhook processing")
            print("4. Verify MotionEye can reach http://localhost:8001")
        elif recent_count > 0:
            print("[SUCCESS] Webhooks are working!")
            print(f"Found {recent_count} detection(s) in the last hour.")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_detections()
