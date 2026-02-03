#!/usr/bin/env python3
"""Debug cameras endpoint to see what's happening"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Camera
from routers.cameras import CameraResponse
from datetime import datetime

def debug_cameras():
    """Debug camera processing"""
    db = SessionLocal()
    try:
        print("=" * 60)
        print("Debugging Cameras Processing")
        print("=" * 60)
        print()
        
        # Get all cameras from database
        cameras = db.query(Camera).all()
        print(f"Database query returned {len(cameras)} cameras")
        print()
        
        result = []
        for i, camera in enumerate(cameras, 1):
            print(f"[{i}/{len(cameras)}] Processing camera {camera.id}: {camera.name}")
            try:
                camera_name = str(camera.name).strip() if camera.name and str(camera.name).strip() else "Unnamed Camera"
                camera_url = str(camera.url).strip() if camera.url and str(camera.url).strip() else "rtsp://localhost"
                
                camera_dict = {
                    "id": camera.id,
                    "name": camera_name,
                    "url": camera_url,
                    "is_active": camera.is_active if camera.is_active is not None else True,
                    "width": max(320, min(7680, int(camera.width) if camera.width is not None else 1280)),
                    "height": max(240, min(4320, int(camera.height) if camera.height is not None else 720)),
                    "framerate": max(1, min(120, int(camera.framerate) if camera.framerate is not None else 30)),
                    "stream_port": max(1024, min(65535, int(camera.stream_port) if camera.stream_port is not None else 8081)),
                    "stream_quality": max(1, min(100, int(camera.stream_quality) if camera.stream_quality is not None else 100)),
                    "stream_maxrate": max(1, min(120, int(camera.stream_maxrate) if camera.stream_maxrate is not None else 30)),
                    "stream_localhost": camera.stream_localhost if camera.stream_localhost is not None else False,
                    "detection_enabled": camera.detection_enabled if camera.detection_enabled is not None else True,
                    "detection_threshold": max(0, min(100000, int(camera.detection_threshold) if camera.detection_threshold is not None else 1500)),
                    "detection_smart_mask_speed": max(0, min(100, int(camera.detection_smart_mask_speed) if camera.detection_smart_mask_speed is not None else 10)),
                    "movie_output": camera.movie_output if camera.movie_output is not None else True,
                    "movie_quality": max(1, min(100, int(camera.movie_quality) if camera.movie_quality is not None else 100)),
                    "movie_codec": "mkv",
                    "snapshot_interval": max(0, min(3600, int(camera.snapshot_interval) if camera.snapshot_interval is not None else 0)),
                    "target_dir": str(camera.target_dir).strip() if camera.target_dir and str(camera.target_dir).strip() else "./motioneye_media",
                    "created_at": camera.created_at if camera.created_at else datetime.utcnow(),
                    "stream_url": None,
                    "mjpeg_url": None,
                    "detection_count": 0,
                    "last_detection": None,
                    "status": "active" if (camera.is_active if camera.is_active is not None else True) else "inactive",
                    "location": None,
                    "latitude": getattr(camera, 'latitude', None),
                    "longitude": getattr(camera, 'longitude', None),
                    "address": getattr(camera, 'address', None),
                }
                
                # Validate
                camera_response = CameraResponse(**camera_dict)
                result.append(camera_response)
                print(f"  [OK] Added to result (total: {len(result)})")
            except Exception as e:
                print(f"  [ERROR] {e}")
                import traceback
                traceback.print_exc()
        
        print()
        print("=" * 60)
        print(f"Final result: {len(result)} cameras")
        print("=" * 60)
        for cam in result:
            print(f"  Camera {cam.id}: {cam.name}")
            
    finally:
        db.close()

if __name__ == "__main__":
    debug_cameras()
