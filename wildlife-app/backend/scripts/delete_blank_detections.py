#!/usr/bin/env python3
"""Script to delete all 'blank' detections from the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import SessionLocal, Detection
from sqlalchemy import func

def delete_blank_detections():
    db = SessionLocal()
    try:
        # Find all detections with "blank" in the species name (case-insensitive)
        # This includes both exact "blank" and taxonomy strings containing "blank"
        blank_detections = db.query(Detection).filter(
            Detection.species.ilike("%blank%")
        ).all()
        
        print(f"Found {len(blank_detections)} blank detections to delete")
        
        if blank_detections:
            for detection in blank_detections:
                species_display = detection.species[:80] + "..." if len(detection.species) > 80 else detection.species
                print(f"Deleting detection {detection.id}: {species_display} (confidence: {detection.confidence:.2f})")
                db.delete(detection)
            
            db.commit()
            print(f"Successfully deleted {len(blank_detections)} blank detections")
        else:
            print("No blank detections found")
            
    except Exception as e:
        db.rollback()
        print(f"Error deleting blank detections: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    delete_blank_detections()

