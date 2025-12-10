"""Quick check for recent webhook activity"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal
    from sqlalchemy import text
except ImportError:
    from .database import SessionLocal
    from sqlalchemy import text

def check_recent_webhooks():
    """Check for webhook activity in the last hour"""
    db = SessionLocal()
    try:
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        # Check webhook audit logs
        result = db.execute(
            text("""
                SELECT action, timestamp, success, error_message, details
                FROM audit_logs
                WHERE action IN ('WEBHOOK', 'WEBHOOK_ERROR', 'WEBHOOK_IGNORED')
                AND timestamp >= :start_time
                ORDER BY timestamp DESC
                LIMIT 20
            """),
            {"start_time": one_hour_ago}
        )
        
        webhooks = result.fetchall()
        
        print("=" * 60)
        print("Recent Webhook Activity (Last Hour)")
        print("=" * 60)
        
        if not webhooks:
            print("❌ NO WEBHOOKS RECEIVED in the last hour!")
            print("\nThis means MotionEye is NOT sending webhooks to the backend.")
            print("\nPossible causes:")
            print("1. MotionEye config not reloaded (needs restart)")
            print("2. Webhook command not executing (check MotionEye logs)")
            print("3. MotionEye cannot reach backend (network issue)")
            print("\nSolutions:")
            print("1. Restart MotionEye: docker restart wildlife-motioneye")
            print("2. Check MotionEye logs: docker logs wildlife-motioneye | grep webhook")
            print("3. Verify webhook URL in camera configs")
        else:
            print(f"✓ Found {len(webhooks)} webhook(s) in the last hour:\n")
            for w in webhooks:
                status = "✓" if w.success else "✗"
                action = w.action
                timestamp = w.timestamp.strftime('%H:%M:%S') if isinstance(w.timestamp, datetime) else str(w.timestamp)
                print(f"  {status} {action} at {timestamp}")
                if w.error_message:
                    print(f"    Error: {w.error_message[:100]}")
        
        # Check recent detections
        detections_result = db.execute(
            text("""
                SELECT COUNT(*) as count
                FROM detections
                WHERE timestamp >= :start_time
            """),
            {"start_time": one_hour_ago}
        )
        detection_count = detections_result.scalar()
        
        print("\n" + "=" * 60)
        print(f"Recent Detections (Last Hour): {detection_count}")
        print("=" * 60)
        
        if len(webhooks) > 0 and detection_count == 0:
            print("\n⚠️  WEBHOOKS RECEIVED BUT NO DETECTIONS CREATED!")
            print("   This means webhooks are reaching the backend but failing.")
            print("   Check the error messages above for details.")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_webhooks()

