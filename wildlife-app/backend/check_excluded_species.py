#!/usr/bin/env python3
"""Check if excluded species filter is removing all detections"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Detection
from routers.settings import get_setting

def check_excluded_species():
    """Check excluded species setting"""
    db = SessionLocal()
    try:
        print("=" * 60)
        print("Checking Excluded Species Filter")
        print("=" * 60)
        print()
        
        # Get excluded species setting
        try:
            excluded_species = get_setting(db, "excluded_species", default=[])
            print(f"Excluded species setting: {excluded_species}")
            print(f"Type: {type(excluded_species)}")
            if isinstance(excluded_species, list):
                print(f"Count: {len(excluded_species)}")
                for species in excluded_species:
                    print(f"  - {species}")
        except Exception as e:
            print(f"Error getting excluded species: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Check total detections
        total = db.query(Detection).count()
        print(f"Total detections in database: {total}")
        
        # Check detections by species
        from sqlalchemy import func
        species_counts = db.query(
            Detection.species,
            func.count(Detection.id).label('count')
        ).group_by(Detection.species).order_by(func.count(Detection.id).desc()).limit(10).all()
        
        print()
        print("Top 10 species:")
        for species, count in species_counts:
            print(f"  {species}: {count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_excluded_species()
