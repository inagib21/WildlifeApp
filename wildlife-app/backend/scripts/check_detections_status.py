#!/usr/bin/env python3
"""Quick check for recent detection activity"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal, Detection
    from sqlalchemy import text
except ImportError:
    from .database import SessionLocal, Detection
    from sqlalchemy import text

def check_detections_status():
    """Check for detection activity in the last 10 minutes"""
    db = SessionLocal()
    try:
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        
        # Check recent detections
        recent_detections = db.query(Detection).filter(
            Detection.timestamp >= ten_minutes_ago
        ).order_by(Detection.timestamp.desc()).all()
        
        print("=" * 60)
        print("Recent Detection Activity (Last 10 Minutes)")
        print("=" * 60)
        
        if not recent_detections:
            print("NO DETECTIONS in the last 10 minutes!")
            print("\nPossible causes:")
            print("1. No motion detected by cameras")
            print("2. Webhooks not being sent from MotionEye")
            print("3. Backend not processing webhooks")
            print("4. SpeciesNet service not responding")
        else:
            print(f"Found {len(recent_detections)} detection(s) in the last 10 minutes:\n")
            for d in recent_detections[:10]:  # Show first 10
                time_ago = datetime.now() - d.timestamp
                minutes_ago = int(time_ago.total_seconds() / 60)
                print(f"  Detection #{d.id}: {d.species} ({d.confidence:.1%}) - {minutes_ago} min ago")
        
        # Check webhook audit logs
        one_hour_ago = datetime.now() - timedelta(hours=1)
        result = db.execute(
            text("""
                SELECT action, timestamp, success, error_message
                FROM audit_logs
                WHERE action IN ('WEBHOOK', 'WEBHOOK_ERROR', 'WEBHOOK_IGNORED')
                AND timestamp >= :start_time
                ORDER BY timestamp DESC
                LIMIT 10
            """),
            {"start_time": one_hour_ago}
        )
        
        webhooks = result.fetchall()
        
        print("\n" + "=" * 60)
        print("Recent Webhook Activity (Last Hour)")
        print("=" * 60)
        
        if not webhooks:
            print("NO WEBHOOKS received in the last hour!")
            print("\nThis means MotionEye is NOT sending webhooks.")
            print("Check MotionEye configuration and restart if needed.")
        else:
            print(f"Found {len(webhooks)} webhook(s) in the last hour:\n")
            for w in webhooks:
                status = "OK" if w.success else "FAILED"
                timestamp = w.timestamp.strftime('%H:%M:%S') if isinstance(w.timestamp, datetime) else str(w.timestamp)
                print(f"  {status} {w.action} at {timestamp}")
                if w.error_message:
                    print(f"    Error: {w.error_message[:80]}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_detections_status()

