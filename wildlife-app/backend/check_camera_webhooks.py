#!/usr/bin/env python3
"""Check webhook configuration and connectivity for cameras"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal, Camera, AuditLog
    from sqlalchemy import func, desc
except ImportError:
    from .database import SessionLocal, Camera, AuditLog
    from sqlalchemy import func, desc

def check_camera_webhooks():
    """Check webhook activity for each camera"""
    db = SessionLocal()
    try:
        cameras = db.query(Camera).order_by(Camera.id).all()
        
        print("=" * 80)
        print("Camera Webhook Activity Check")
        print("=" * 80)
        print(f"\nAnalysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        day_ago = datetime.now() - timedelta(hours=24)
        
        for cam in cameras:
            print(f"\n{'='*80}")
            print(f"Camera {cam.id}: {cam.name}")
            print(f"{'='*80}")
            
            # Check for webhook audit logs
            webhook_logs = db.query(AuditLog).filter(
                AuditLog.action == 'webhook_received',
                AuditLog.timestamp >= day_ago
            ).order_by(desc(AuditLog.timestamp)).all()
            
            # Filter logs for this camera
            camera_webhooks = []
            for log in webhook_logs:
                # Try to extract camera_id from log details
                if log.details:
                    import json
                    try:
                        details = json.loads(log.details) if isinstance(log.details, str) else log.details
                        if isinstance(details, dict):
                            log_camera_id = details.get('camera_id') or details.get('cameraId')
                            if log_camera_id and int(log_camera_id) == cam.id:
                                camera_webhooks.append(log)
                    except:
                        pass
            
            if camera_webhooks:
                print(f"  Webhooks received (last 24h): {len(camera_webhooks)}")
                latest = camera_webhooks[0]
                hours_ago = (datetime.now() - latest.timestamp).total_seconds() / 3600
                print(f"  Last webhook: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({hours_ago:.1f} hours ago)")
            else:
                print(f"  WARNING: No webhooks received in last 24 hours!")
                print(f"  Possible issues:")
                print(f"    - MotionEye not detecting motion for this camera")
                print(f"    - Camera stream not connected")
                print(f"    - Webhook script not configured correctly")
                print(f"    - MotionEye service not running")
            
            # Check detections
            detections = db.query(func.count()).filter(
                func.cast(func.extract('epoch', func.now() - func.cast(func.max(AuditLog.timestamp), type(None))), type(None)) == None
            ).scalar()
            
            recent_detections = db.query(func.count()).filter(
                AuditLog.action == 'detection_created',
                AuditLog.timestamp >= day_ago
            ).scalar()
            
            print(f"  Status: {'Active' if cam.is_active else 'Inactive'}")
            print(f"  URL: {cam.url}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_camera_webhooks()

