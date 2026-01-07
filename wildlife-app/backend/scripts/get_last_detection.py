#!/usr/bin/env python3
"""Get the timestamp of the last detection"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal, Detection
except ImportError:
    from .database import SessionLocal, Detection

def get_last_detection():
    """Get the most recent detection"""
    db = SessionLocal()
    try:
        last_detection = db.query(Detection).order_by(Detection.timestamp.desc()).first()
        
        if not last_detection:
            print("No detections found in database.")
            return
        
        now = datetime.now()
        time_diff = now - last_detection.timestamp
        
        # Calculate time difference
        days = time_diff.days
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print("=" * 60)
        print("Last Detection")
        print("=" * 60)
        print(f"Detection ID: {last_detection.id}")
        print(f"Species: {last_detection.species}")
        print(f"Confidence: {last_detection.confidence:.1%}")
        print(f"Camera ID: {last_detection.camera_id}")
        print(f"\nTimestamp: {last_detection.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Time ago: ", end="")
        
        if days > 0:
            print(f"{days} day{'s' if days != 1 else ''}, ", end="")
        if hours > 0:
            print(f"{hours} hour{'s' if hours != 1 else ''}, ", end="")
        if minutes > 0:
            print(f"{minutes} minute{'s' if minutes != 1 else ''}, ", end="")
        print(f"{seconds} second{'s' if seconds != 1 else ''} ago")
        
    finally:
        db.close()

if __name__ == "__main__":
    get_last_detection()

