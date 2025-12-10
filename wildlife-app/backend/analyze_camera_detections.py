#!/usr/bin/env python3
"""Analyze camera detection statistics and identify issues"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import SessionLocal, Detection, Camera
    from sqlalchemy import func
except ImportError:
    from .database import SessionLocal, Detection, Camera
    from sqlalchemy import func

def analyze_camera_detections():
    """Analyze detection statistics for all cameras"""
    db = SessionLocal()
    try:
        cameras = db.query(Camera).order_by(Camera.id).all()
        
        print("=" * 80)
        print("Camera Detection Analysis")
        print("=" * 80)
        
        now = datetime.now()
        day_ago = now - timedelta(hours=24)
        week_ago = now - timedelta(days=7)
        
        print(f"\nAnalysis Time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        cameras_with_issues = []
        cameras_working = []
        
        for cam in cameras:
            # Get detection counts
            total = db.query(Detection).filter(Detection.camera_id == cam.id).count()
            last_24h = db.query(Detection).filter(
                Detection.camera_id == cam.id,
                Detection.timestamp >= day_ago
            ).count()
            last_week = db.query(Detection).filter(
                Detection.camera_id == cam.id,
                Detection.timestamp >= week_ago
            ).count()
            
            # Get last detection time
            last_detection = db.query(Detection).filter(
                Detection.camera_id == cam.id
            ).order_by(Detection.timestamp.desc()).first()
            
            last_detection_time = last_detection.timestamp if last_detection else None
            time_since_last = (now - last_detection_time) if last_detection_time else None
            
            # Get species breakdown
            species_counts = db.query(
                Detection.species,
                func.count(Detection.id).label('count')
            ).filter(
                Detection.camera_id == cam.id,
                Detection.timestamp >= week_ago
            ).group_by(Detection.species).order_by(func.count(Detection.id).desc()).limit(5).all()
            
            print(f"\n{'='*80}")
            print(f"Camera {cam.id}: {cam.name}")
            print(f"{'='*80}")
            status_icon = "Active" if cam.is_active else "Inactive"
            print(f"  Status: {status_icon}")
            print(f"  Total Detections: {total}")
            print(f"  Last 24 Hours: {last_24h}")
            print(f"  Last 7 Days: {last_week}")
            
            if last_detection_time:
                hours_ago = time_since_last.total_seconds() / 3600
                print(f"  Last Detection: {last_detection_time.strftime('%Y-%m-%d %H:%M:%S')} ({hours_ago:.1f} hours ago)")
                
                if hours_ago > 24:
                    print(f"  WARNING: No detections in last 24 hours!")
                    cameras_with_issues.append({
                        'camera': cam,
                        'issue': 'no_recent_detections',
                        'hours_ago': hours_ago
                    })
                elif last_24h == 0:
                    print(f"  WARNING: No detections in last 24 hours!")
                    cameras_with_issues.append({
                        'camera': cam,
                        'issue': 'no_detections_24h',
                        'hours_ago': hours_ago
                    })
                else:
                    cameras_working.append(cam)
            else:
                print(f"  ERROR: NO DETECTIONS EVER!")
                cameras_with_issues.append({
                    'camera': cam,
                    'issue': 'no_detections_ever',
                    'hours_ago': None
                })
            
            if species_counts:
                print(f"  Top Species (last 7 days):")
                for species, count in species_counts:
                    print(f"    - {species}: {count}")
        
        print(f"\n{'='*80}")
        print("Summary")
        print(f"{'='*80}")
        print(f"Total Cameras: {len(cameras)}")
        print(f"Working Cameras: {len(cameras_working)}")
        print(f"Cameras with Issues: {len(cameras_with_issues)}")
        
        if cameras_with_issues:
            print(f"\nWARNING: Cameras Needing Attention:")
            for issue in cameras_with_issues:
                cam = issue['camera']
                if issue['issue'] == 'no_detections_ever':
                    print(f"  - Camera {cam.id} ({cam.name}): No detections ever recorded")
                elif issue['issue'] == 'no_detections_24h':
                    print(f"  - Camera {cam.id} ({cam.name}): No detections in last 24 hours")
                elif issue['issue'] == 'no_recent_detections':
                    print(f"  - Camera {cam.id} ({cam.name}): Last detection {issue['hours_ago']:.1f} hours ago")
        
        # Overall statistics
        total_detections_24h = db.query(Detection).filter(Detection.timestamp >= day_ago).count()
        total_detections_week = db.query(Detection).filter(Detection.timestamp >= week_ago).count()
        
        print(f"\n{'='*80}")
        print("Overall Statistics")
        print(f"{'='*80}")
        print(f"Total Detections (Last 24h): {total_detections_24h}")
        print(f"Total Detections (Last 7 days): {total_detections_week}")
        print(f"Average per Camera (24h): {total_detections_24h / len(cameras) if cameras else 0:.1f}")
        print(f"Average per Camera (7 days): {total_detections_week / len(cameras) if cameras else 0:.1f}")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze_camera_detections()

