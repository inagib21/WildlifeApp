#!/usr/bin/env python3
"""Check detections in database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import SessionLocal, Detection, Camera

db = SessionLocal()
try:
    total = db.query(Detection).count()
    print(f'Total detections in database: {total}')
    
    if total > 0:
        print('\n' + '='*80)
        print('Recent detections (last 20):')
        print('='*80)
        
        detections = db.query(Detection).order_by(Detection.timestamp.desc()).limit(20).all()
        
        for d in detections:
            camera = db.query(Camera).filter(Camera.id == d.camera_id).first()
            camera_name = camera.name if camera else f"Camera {d.camera_id}"
            
            print(f"\nID: {d.id}")
            print(f"  Camera: {camera_name} (ID: {d.camera_id})")
            print(f"  Species: {d.species}")
            print(f"  Confidence: {d.confidence:.2%}")
            print(f"  Timestamp: {d.timestamp}")
            print(f"  Image Path: {d.image_path}")
            if d.image_width and d.image_height:
                print(f"  Image Size: {d.image_width}x{d.image_height}")
        
        print('\n' + '='*80)
        print('Detections by Camera:')
        print('='*80)
        
        from sqlalchemy import func
        camera_counts = db.query(Detection.camera_id, func.count(Detection.id).label('count')).group_by(Detection.camera_id).all()
        
        for cam_id, count in camera_counts:
            camera = db.query(Camera).filter(Camera.id == cam_id).first()
            camera_name = camera.name if camera else f"Camera {cam_id}"
            print(f"  {camera_name} (ID: {cam_id}): {count} detections")
        
        print('\n' + '='*80)
        print('Detections by Species:')
        print('='*80)
        
        species_counts = db.query(Detection.species, func.count(Detection.id).label('count')).group_by(Detection.species).order_by(func.count(Detection.id).desc()).all()
        
        for species, count in species_counts:
            print(f"  {species}: {count} detections")
    else:
        print('\nNo detections found in database yet.')
        print('Once Camera 6 detects motion, detections will appear here.')
        
finally:
    db.close()

