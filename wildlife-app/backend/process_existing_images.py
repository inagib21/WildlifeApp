#!/usr/bin/env python3
"""Process existing images from Camera6 that haven't been classified yet"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import SessionLocal, Detection, Camera
import os
import json
from datetime import datetime
from pathlib import Path

# Get the wildlife-app directory
wildlife_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
camera6_dir = os.path.join(wildlife_app_dir, "motioneye_media", "Camera6")

db = SessionLocal()
try:
    # Get all existing image paths from database
    existing_paths = set()
    for detection in db.query(Detection).filter(Detection.camera_id == 6).all():
        if detection.image_path:
            existing_paths.add(os.path.normpath(detection.image_path))
    
    print(f"Found {len(existing_paths)} existing detections in database")
    
    # Find all image files in Camera6 directory
    if not os.path.exists(camera6_dir):
        print(f"Camera6 directory not found: {camera6_dir}")
        exit(1)
    
    image_files = []
    for root, dirs, files in os.walk(camera6_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(root, file)
                # Skip the "m" (motion mask) files - these are debug images, not actual photos
                filename_lower = file.lower()
                if not (filename_lower.endswith('m.jpg') or filename_lower.endswith('m.jpeg')):
                    image_files.append(full_path)
    
    print(f"Found {len(image_files)} image files in Camera6 directory")
    
    # Filter out already processed images
    unprocessed = [f for f in image_files if os.path.normpath(f) not in existing_paths]
    print(f"Found {len(unprocessed)} unprocessed images")
    
    if unprocessed:
        print(f"\nProcessing first 10 images as a test...")
        from services.ai_backends import ai_backend_manager
        
        processed = 0
        for image_path in unprocessed[:10]:
            try:
                print(f"\nProcessing: {os.path.basename(image_path)}")
                
                # Process with AI Backend Manager
                predictions = ai_backend_manager.predict(image_path)
                
                if "error" in predictions:
                    print(f"  SpeciesNet error: {predictions['error']}")
                    species = "Unknown"
                    confidence = 0.0
                else:
                    # Extract species prediction
                    species = "Unknown"
                    confidence = 0.0
                    
                    if isinstance(predictions, dict):
                        if "predictions" in predictions and predictions["predictions"]:
                            pred = predictions["predictions"][0]
                            species = pred.get("prediction", "Unknown")
                            confidence = pred.get("prediction_score", 0.0)
                    
                    # Clean up species name
                    if species and ";" in species:
                        parts = species.split(";")
                        if len(parts) >= 3:
                            species = f"{parts[-2].title()} {parts[-1].title()}"
                        else:
                            species = parts[-1].title()
                
                # Save detection to database
                detection_data = {
                    "camera_id": 6,
                    "timestamp": datetime.fromtimestamp(os.path.getmtime(image_path)),
                    "species": species,
                    "confidence": confidence,
                    "image_path": image_path,
                    "detections_json": json.dumps(predictions),
                    "prediction_score": confidence
                }
                
                db_detection = Detection(**detection_data)
                db.add(db_detection)
                processed += 1
                
                print(f"  Saved: {species} ({confidence:.2%})")
                
            except Exception as e:
                print(f"  Error processing {image_path}: {e}")
        
        db.commit()
        print(f"\nProcessed and saved {processed} detections to database")
        print(f"  Run this script again to process more images")
    else:
        print("\nAll images have already been processed!")
        
finally:
    db.close()

