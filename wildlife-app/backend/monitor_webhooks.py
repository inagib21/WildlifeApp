"""Monitor webhook activity in real-time"""
import sys
import os
import time
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal, AuditLog, Detection
except ImportError:
    from .database import SessionLocal, AuditLog, Detection

def monitor_webhooks(duration_minutes=5):
    """Monitor webhook activity for specified duration"""
    print("=" * 60)
    print(f"Webhook Activity Monitor (Monitoring for {duration_minutes} minutes)")
    print("=" * 60)
    print("Press Ctrl+C to stop early\n")
    
    db = SessionLocal()
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    # Get initial counts (using raw SQL to avoid schema issues)
    initial_webhooks = db.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE action IN ('WEBHOOK', 'WEBHOOK_ERROR', 'WEBHOOK_IGNORED') AND timestamp >= %s",
        (start_time - timedelta(minutes=1),)
    ).scalar()
    
    initial_detections = db.query(Detection).filter(
        Detection.timestamp >= start_time - timedelta(minutes=1)
    ).count()
    
    print(f"Starting at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Initial webhook count (last 1 min): {initial_webhooks}")
    print(f"Initial detection count (last 1 min): {initial_detections}\n")
    print("Monitoring for webhook activity...\n")
    
    last_webhook_count = initial_webhooks
    last_detection_count = initial_detections
    
    try:
        while datetime.now() < end_time:
            time.sleep(10)  # Check every 10 seconds
            
            # Check for new webhooks (using raw SQL)
            current_time = datetime.now()
            recent_webhooks_result = db.execute(
                "SELECT id, action, timestamp, success, error_message FROM audit_logs WHERE action IN ('WEBHOOK', 'WEBHOOK_ERROR', 'WEBHOOK_IGNORED') AND timestamp >= %s ORDER BY timestamp DESC",
                (start_time,)
            ).fetchall()
            recent_webhooks = [dict(row._mapping) for row in recent_webhooks_result]
            
            recent_detections = db.query(Detection).filter(
                Detection.timestamp >= start_time
            ).order_by(Detection.timestamp.desc()).all()
            
            new_webhooks = len(recent_webhooks) - last_webhook_count
            new_detections = len(recent_detections) - last_detection_count
            
            if new_webhooks > 0 or new_detections > 0:
                print(f"[{current_time.strftime('%H:%M:%S')}] Activity detected!")
                if new_webhooks > 0:
                    print(f"  → {new_webhooks} new webhook(s)")
                    for webhook in recent_webhooks[:new_webhooks]:
                        status = "✓" if webhook.get('success', True) else "✗"
                        action = webhook.get('action', 'UNKNOWN')
                        timestamp = webhook.get('timestamp', current_time)
                        if isinstance(timestamp, datetime):
                            time_str = timestamp.strftime('%H:%M:%S')
                        else:
                            time_str = str(timestamp)
                        print(f"    {status} {action} - {time_str}")
                        if webhook.get('error_message'):
                            print(f"      Error: {webhook['error_message'][:100]}")
                if new_detections > 0:
                    print(f"  → {new_detections} new detection(s)")
                    for detection in recent_detections[:new_detections]:
                        print(f"    ✓ Detection ID {detection.id} - Camera {detection.camera_id} - {detection.species}")
                
                last_webhook_count = len(recent_webhooks)
                last_detection_count = len(recent_detections)
            else:
                elapsed = (current_time - start_time).total_seconds()
                remaining = (end_time - current_time).total_seconds()
                print(f"[{current_time.strftime('%H:%M:%S')}] No activity... ({int(remaining)}s remaining)")
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    
    finally:
        db.close()
        
        # Final summary (using raw SQL)
        db = SessionLocal()
        final_webhooks = db.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE action IN ('WEBHOOK', 'WEBHOOK_ERROR', 'WEBHOOK_IGNORED') AND timestamp >= %s",
            (start_time,)
        ).scalar()
        
        final_detections = db.query(Detection).filter(
            Detection.timestamp >= start_time
        ).count()
        
        print("\n" + "=" * 60)
        print("Summary:")
        print("=" * 60)
        print(f"Total webhooks during monitoring: {final_webhooks}")
        print(f"Total detections during monitoring: {final_detections}")
        
        if final_webhooks == 0:
            print("\n⚠️  NO WEBHOOKS RECEIVED!")
            print("   This means MotionEye is not sending webhooks.")
            print("   Possible causes:")
            print("   1. MotionEye webhook command is not executing")
            print("   2. MotionEye cannot reach backend (network issue)")
            print("   3. MotionEye webhook configuration is incorrect")
            print("\n   Next steps:")
            print("   1. Check MotionEye logs: docker logs wildlife-motioneye | grep webhook")
            print("   2. Verify webhook URL in camera configs")
            print("   3. Test webhook manually from MotionEye container")
        elif final_webhooks > 0 and final_detections == 0:
            print("\n⚠️  WEBHOOKS RECEIVED BUT NO DETECTIONS CREATED!")
            print("   This means webhooks are reaching the backend but failing.")
            print("   Check error statistics: GET /api/debug/error-statistics")
        else:
            print("\n✓ System is working correctly!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor webhook activity")
    parser.add_argument("--duration", type=int, default=5, help="Duration in minutes (default: 5)")
    args = parser.parse_args()
    
    monitor_webhooks(args.duration)

