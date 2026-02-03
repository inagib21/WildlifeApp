#!/usr/bin/env python3
"""Script to check camera status in database and MotionEye"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Camera
from services.motioneye import motioneye_client

def check_camera_status():
    """Check camera status from database and MotionEye"""
    db = SessionLocal()
    try:
        print("=" * 60)
        print("Camera Status Check")
        print("=" * 60)
        print()
        
        # Get cameras from database
        db_cameras = db.query(Camera).all()
        print(f"Database cameras: {len(db_cameras)}")
        print()
        
        # Get cameras from MotionEye
        try:
            me_cameras = motioneye_client.get_cameras()
            print(f"MotionEye cameras: {len(me_cameras)}")
            print()
        except Exception as e:
            print(f"Error getting MotionEye cameras: {e}")
            me_cameras = []
        
        # Check each camera
        print("Camera Status Breakdown:")
        print("-" * 60)
        print(f"{'ID':<5} {'Name':<20} {'DB Active':<12} {'ME Enabled':<12} {'Match':<8}")
        print("-" * 60)
        
        active_count = 0
        inactive_count = 0
        mismatch_count = 0
        
        for db_cam in db_cameras:
            # Find corresponding MotionEye camera
            me_cam = next((c for c in me_cameras if c.get("id") == db_cam.id), None)
            
            db_active = db_cam.is_active if db_cam.is_active is not None else True
            me_enabled = me_cam.get("enabled", True) if me_cam else "N/A"
            match = "OK" if (me_cam and me_enabled == db_active) or (not me_cam) else "MISMATCH"
            
            if db_active:
                active_count += 1
            else:
                inactive_count += 1
                
            if me_cam and me_enabled != db_active:
                mismatch_count += 1
            
            print(f"{db_cam.id:<5} {db_cam.name[:18]:<20} {str(db_active):<12} {str(me_enabled):<12} {match:<8}")
        
        print("-" * 60)
        print()
        print(f"Summary:")
        print(f"  Active cameras: {active_count}")
        print(f"  Inactive cameras: {inactive_count}")
        print(f"  Status mismatches: {mismatch_count}")
        print()
        
        if mismatch_count > 0:
            print("⚠️  WARNING: Some cameras have mismatched status!")
            print("   Run camera sync to update database from MotionEye.")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_camera_status()
