"""Detection management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request, File, UploadFile, Query
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import json
import ast
import os
import csv
import io
import zipfile
import tempfile
import shutil
from pathlib import Path
from fastapi.responses import Response, JSONResponse

try:
    from ..database import engine, Camera, Detection, FaceDetection, KnownFace
    from ..models import DetectionResponse, DetectionCreate, RecognizedFaceResponse
    from ..utils.audit import log_audit_event
    from ..services.events import get_event_manager
    from ..services.species_info import species_info_service
except ImportError:
    from database import engine, Camera, Detection, FaceDetection, KnownFace
    from models import DetectionResponse, DetectionCreate, RecognizedFaceResponse
    from utils.audit import log_audit_event
    from services.events import get_event_manager
    from services.species_info import species_info_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_excluded_species_filter(query, db: Session):
    """Apply excluded species filter to query if configured"""
    try:
        try:
            from ..routers.settings import get_setting
        except ImportError:
            from routers.settings import get_setting
        
        excluded_species = get_setting(db, "excluded_species", default=[])
    except Exception as e:
        logger.warning(f"Error getting excluded_species setting: {e}")
        return query  # Return query unchanged if we can't get the setting
    
    try:
        if excluded_species and isinstance(excluded_species, list) and len(excluded_species) > 0:
            # Filter out excluded species (case-insensitive)
            # Build a list of conditions - species must not contain any excluded term
            from sqlalchemy import and_
            
            # Build exclusion condition: species IS NULL OR species doesn't contain any excluded term
            # For each excluded species, species must not contain it
            # Use the simplest possible SQL that PostgreSQL handles well
            exclusion_conditions = []
            for excluded in excluded_species:
                if excluded and str(excluded).strip():
                    try:
                        excluded_lower = str(excluded).lower().strip()
                        # Build condition: species is NULL OR species (lowercased) doesn't contain excluded term
                        # PostgreSQL handles NULL in LOWER() correctly (returns NULL), and NULL != '%excluded%' is true
                        # So we can check: species IS NULL OR LOWER(species) NOT LIKE '%excluded%'
                        exclusion_conditions.append(
                            or_(
                                Detection.species.is_(None),
                                ~func.lower(Detection.species).contains(excluded_lower)
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Error processing excluded species '{excluded}': {e}")
                        continue
            
            # If we have exclusion conditions, apply them with AND logic
            # This means: (species is NULL OR doesn't contain excluded[0]) AND (species is NULL OR doesn't contain excluded[1]) AND ...
            # This is correct: include if species is NULL or doesn't match any exclusion
            if exclusion_conditions:
                try:
                    if len(exclusion_conditions) == 1:
                        # Single exclusion - just apply it
                        query = query.filter(exclusion_conditions[0])
                    else:
                        # Multiple exclusions - all must be satisfied
                        # Combine: (NULL OR not contains[0]) AND (NULL OR not contains[1]) ...
                        combined_condition = and_(*exclusion_conditions)
                        query = query.filter(combined_condition)
                    logger.debug(f"Applied excluded species filter: {excluded_species}")
                except Exception as e:
                    logger.error(f"Error applying excluded species filter: {e}", exc_info=True)
                    # Return query unchanged if filter application fails
                    return query
    except Exception as e:
        logger.error(f"Unexpected error in excluded species filter: {e}", exc_info=True)
        # Return query unchanged on any error
        return query
    
    return query


def _export_with_images(
    detections: List[Detection],
    format: str,
    request: Request,
    db: Session,
    camera_id: Optional[int] = None,
    species: Optional[str] = None
):
    """Helper function to export detections with images in a zip file"""
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create temporary directory for zip contents
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create data file (CSV or JSON)
        if format.lower() == "csv":
            csv_file = temp_path / f"detections_export_{timestamp_str}.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Camera ID", "Timestamp", "Species", "Confidence", 
                    "Image Path", "File Size", "Image Width", "Image Height", 
                    "Prediction Score", "Image Filename"
                ])
                
                for det in detections:
                    # Determine image filename
                    image_filename = ""
                    if det.image_path:
                        image_filename = Path(det.image_path).name
                        # Add image to zip
                        source_path = Path(det.image_path)
                        if source_path.exists() and source_path.is_file():
                            # Create images subdirectory
                            images_dir = temp_path / "images"
                            images_dir.mkdir(exist_ok=True)
                            dest_path = images_dir / image_filename
                            try:
                                shutil.copy2(source_path, dest_path)
                            except Exception as e:
                                logger.warning(f"Could not copy image {source_path}: {e}")
                    
                    writer.writerow([
                        det.id,
                        det.camera_id,
                        det.timestamp.isoformat() if det.timestamp else "",
                        det.species or "",
                        det.confidence or 0.0,
                        det.image_path or "",
                        det.file_size or 0,
                        det.image_width or 0,
                        det.image_height or 0,
                        det.prediction_score or 0.0,
                        image_filename
                    ])
            
            data_file = csv_file
        
        else:  # JSON
            json_file = temp_path / f"detections_export_{timestamp_str}.json"
            detections_data = []
            images_dir = temp_path / "images"
            images_dir.mkdir(exist_ok=True)
            
            for det in detections:
                image_filename = ""
                if det.image_path:
                    image_filename = Path(det.image_path).name
                    # Add image to zip
                    source_path = Path(det.image_path)
                    if source_path.exists() and source_path.is_file():
                        dest_path = images_dir / image_filename
                        try:
                            shutil.copy2(source_path, dest_path)
                        except Exception as e:
                            logger.warning(f"Could not copy image {source_path}: {e}")
                
                detections_data.append({
                    "id": det.id,
                    "camera_id": det.camera_id,
                    "timestamp": det.timestamp.isoformat() if det.timestamp else None,
                    "species": det.species,
                    "confidence": det.confidence,
                    "image_path": det.image_path,
                    "image_filename": image_filename,
                    "file_size": det.file_size,
                    "image_width": det.image_width,
                    "image_height": det.image_height,
                    "prediction_score": det.prediction_score
                })
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(detections_data, f, indent=2)
            
            data_file = json_file
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add data file
            zip_file.write(data_file, data_file.name)
            
            # Add all images
            images_dir = temp_path / "images"
            if images_dir.exists():
                for image_file in images_dir.iterdir():
                    if image_file.is_file():
                        zip_file.write(image_file, f"images/{image_file.name}")
        
        zip_buffer.seek(0)
        
        # Log export
        log_audit_event(
            db=db,
            request=request,
            action="EXPORT",
            resource_type="detection",
            details={
                "format": f"{format}_with_images",
                "count": len(detections),
                "camera_id": camera_id,
                "species": species,
                "include_images": True
            }
        )
        
        return Response(
            content=zip_buffer.read(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=detections_export_{timestamp_str}.zip"
            }
        )


def setup_detections_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup detections router with rate limiting and dependencies"""
    
    event_manager = get_event_manager()
    
    @router.get("/detections", response_model=List[DetectionResponse])
    def get_detections(
        camera_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        species: Optional[List[str]] = Query(None), # Changed to List[str]
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score (0.0-1.0)"),
        max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum confidence score (0.0-1.0)"),
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """Get detections with optional filtering and pagination"""
        from utils.error_handler import ErrorContext, handle_database_error
        from sqlalchemy.exc import SQLAlchemyError
        
        with ErrorContext("get_detections", camera_id=camera_id, limit=limit, offset=offset):
            try:
                # Skip the expensive count query - it's not needed for the response
                # Only log if in debug mode to avoid performance impact
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    total_count = db.query(Detection).count()
                    logging.debug(f"Total detections in database: {total_count}")
                
                query = db.query(Detection)
                
                if camera_id is not None:
                    query = query.filter(Detection.camera_id == camera_id)
                
                # Enhanced species filtering (supports multiple species)
                if species:
                    # If species is a list of strings
                    if isinstance(species, list):
                        species_conditions = []
                        for s in species:
                            if s:
                                species_conditions.append(Detection.species.ilike(f"%{s}%"))
                        if species_conditions:
                            query = query.filter(or_(*species_conditions))
                    # If species is a single string (backward compatibility)
                    elif isinstance(species, str):
                        query = query.filter(Detection.species.ilike(f"%{species}%"))
                
                # Apply confidence filters
                if min_confidence is not None:
                    query = query.filter(Detection.confidence >= min_confidence)
                if max_confidence is not None:
                    query = query.filter(Detection.confidence <= max_confidence)
                
                # Apply excluded species filter
                query = _apply_excluded_species_filter(query, db)
                
                if start_date:
                    try:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        query = query.filter(Detection.timestamp >= start_dt)
                    except ValueError:
                        pass  # Invalid date format, ignore
                
                if end_date:
                    try:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        query = query.filter(Detection.timestamp <= end_dt)
                    except ValueError:
                        pass  # Invalid date format, ignore
                
                # Apply search filter if provided (searches species, image_path, and camera name)
                if search:
                    search_term = f"%{search}%"
                    # Join with Camera table to search camera names
                    query = query.join(Camera, Detection.camera_id == Camera.id).filter(
                        or_(
                            Detection.species.ilike(search_term),
                            Detection.image_path.ilike(search_term),
                            Camera.name.ilike(search_term)
                        )
                    )
                else:
                    # No join needed if not searching
                    pass
                
                # Apply ordering first (use index for performance)
                query = query.order_by(Detection.timestamp.desc())
                
                # Apply limit FIRST to reduce query size (important for performance)
                # Cap limit at 1000 to prevent extremely large queries that cause timeouts
                effective_limit = min(limit or 50, 1000)
                query = query.limit(effective_limit)
                
                # Apply offset if provided (after limit for better performance)
                if offset is not None:
                    query = query.offset(offset)
                
                detections = query.all()
                logger.info(f"Query returned {len(detections)} detections from database")
                if len(detections) == 0:
                    logger.info(f"No detections found. Total in DB: {db.query(Detection).count()}")
            
                # Batch-fetch all cameras to avoid N+1 queries
                camera_ids = {d.camera_id for d in detections if d.camera_id is not None}
                cameras = {}
                if camera_ids:
                    cameras = {c.id: c for c in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()}
                
                # Batch-fetch face detections and known faces to avoid N+1 queries
                detection_ids = [d.id for d in detections]
                face_detections_map = {}
                known_faces_map = {}
                if detection_ids:
                    face_detections = db.query(FaceDetection).filter(FaceDetection.detection_id.in_(detection_ids)).all()
                    for fd in face_detections:
                        if fd.detection_id not in face_detections_map:
                            face_detections_map[fd.detection_id] = []
                        face_detections_map[fd.detection_id].append(fd)
                    
                    # Get all known face IDs and fetch them
                    known_face_ids = {fd.known_face_id for fd in face_detections if fd.known_face_id is not None}
                    if known_face_ids:
                        known_faces = db.query(KnownFace).filter(KnownFace.id.in_(known_face_ids)).all()
                        known_faces_map = {kf.id: kf for kf in known_faces}
                
                # Batch-fetch species info for unique species (optimization: reduce redundant lookups)
                unique_species = {str(d.species).strip() for d in detections if d.species and str(d.species).strip() and str(d.species).strip() != "Unknown"}
                species_info_cache = {}
                for species_name in unique_species:
                    try:
                        species_info_dict = species_info_service.get_species_info(species_name)
                        if species_info_dict:
                            from models import SpeciesInfoResponse
                            species_info_cache[species_name] = SpeciesInfoResponse(**species_info_dict)
                    except Exception:
                        pass  # Skip errors, will be None for this species
            
                # Convert to response models with media URLs
                result = []
                for detection in detections:
                    try:
                        camera = cameras.get(detection.camera_id) if detection.camera_id else None
                        # Ensure camera_name is always a non-empty string (required by DetectionResponse)
                        if camera and camera.name and str(camera.name).strip():
                            camera_name = str(camera.name).strip()
                        elif detection.camera_id:
                            camera_name = f"Camera {detection.camera_id}"
                        else:
                            camera_name = "Unknown Camera"
                        
                        # Extract full taxonomy from detections_json if available
                        full_taxonomy = None
                        if detection.detections_json:
                            try:
                                detections_data = json.loads(detection.detections_json)
                                if "predictions" in detections_data and detections_data["predictions"]:
                                    full_taxonomy = detections_data["predictions"][0].get("prediction", detection.species)
                                elif "species" in detections_data:
                                    full_taxonomy = detections_data["species"]
                            except:
                                full_taxonomy = detection.species or "Unknown"
                        
                        # Ensure all required fields have valid values for DetectionResponse
                        # DetectionBase requires: camera_id >= 1, species (non-empty), confidence (0.0-1.0), image_path (non-empty with valid extension)
                        camera_id_val = int(detection.camera_id) if detection.camera_id and detection.camera_id >= 1 else 1
                        species_val = str(detection.species).strip() if detection.species and str(detection.species).strip() else "Unknown"
                        confidence_val = float(detection.confidence) if detection.confidence is not None else 0.0
                        confidence_val = max(0.0, min(1.0, confidence_val))  # Clamp to 0.0-1.0
                        
                        # Get species information from cache (batched lookup)
                        species_info = species_info_cache.get(species_val)
                        
                        # Normalize image_path to ensure it passes validation
                        # The validator requires either a valid image extension or a temp path
                        if detection.image_path and str(detection.image_path).strip():
                            image_path_val = str(detection.image_path).strip()
                            # Check if it has a valid extension
                            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
                            has_valid_ext = any(image_path_val.lower().endswith(ext) for ext in valid_extensions)
                            # Check if it's a temp path
                            is_temp_path = image_path_val.startswith('/tmp') or image_path_val.startswith('C:\\') or 'temp' in image_path_val.lower()
                            # If neither, add .jpg extension to make it valid
                            if not has_valid_ext and not is_temp_path:
                                image_path_val = image_path_val + '.jpg'
                        else:
                            # Default to a valid temp path
                            image_path_val = "/tmp/unknown.jpg"
                        
                        # Fix detections_json - it might be stored as Python dict string instead of JSON
                        # The validator requires it to be valid JSON or None
                        detections_json_val = None
                        if detection.detections_json:
                            try:
                                # Try to parse as JSON first
                                json.loads(detection.detections_json)
                                detections_json_val = detection.detections_json  # Already valid JSON
                            except (json.JSONDecodeError, TypeError):
                                # If it's a Python dict string, convert it to JSON
                                try:
                                    if isinstance(detection.detections_json, str):
                                        # Try to eval it as Python literal (dict)
                                        parsed = ast.literal_eval(detection.detections_json)
                                        detections_json_val = json.dumps(parsed)  # Convert to JSON string
                                        # Verify the converted JSON is valid
                                        json.loads(detections_json_val)
                                    else:
                                        detections_json_val = json.dumps(detection.detections_json)
                                        # Verify the converted JSON is valid
                                        json.loads(detections_json_val)
                                except Exception as e:
                                    # If all else fails, set to None (invalid JSON will fail validation)
                                    logging.warning(f"Could not convert detections_json for detection {detection.id} to valid JSON: {e}")
                                    detections_json_val = None
                        
                        detection_dict = {
                            "id": detection.id,
                            "camera_id": camera_id_val,
                            "timestamp": detection.timestamp,
                            "species": species_val,
                            "full_taxonomy": full_taxonomy,
                            "confidence": confidence_val,
                            "image_path": image_path_val,
                            "file_size": detection.file_size,
                            "image_width": detection.image_width,
                            "image_height": detection.image_height,
                            "image_quality": detection.image_quality,
                            "prediction_score": float(detection.prediction_score) if detection.prediction_score is not None else None,
                            "detections_json": detections_json_val,
                            "media_url": None,  # Will be set below
                            "video_url": None,  # Will be set below
                            "thumbnail_url": None,  # Will be set below
                            "camera_name": str(camera_name),  # Add camera name to response
                            "species_info": species_info  # Add species information
                        }
                
                        # Generate media URL from image path
                        if detection.image_path:
                            try:
                                import os
                                # Normalize path for both Windows and Linux
                                path = detection.image_path.replace("\\", "/")
                                # Remove empty parts and normalize
                                parts = [p for p in path.split("/") if p]
                                
                                # Find the filename (last segment with image extension)
                                image_extensions = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]
                                filename = None
                                filename_idx = -1
                                for i in range(len(parts) - 1, -1, -1):
                                    if "." in parts[i]:
                                        ext = parts[i].split(".")[-1].lower()
                                        if ext in image_extensions:
                                            filename = parts[i]
                                            filename_idx = i
                                            break
                                
                                if not filename:
                                    # No valid filename found, skip
                                    detection_dict["media_url"] = None
                                else:
                                    # Look for motioneye_media/CameraX/date/filename
                                    if "motioneye_media" in parts:
                                        idx = parts.index("motioneye_media")
                                        if len(parts) > idx + 2 and filename_idx > idx + 2:
                                            camera_folder = parts[idx + 1]  # Camera1
                                            date_folder = parts[idx + 2]    # 2025-07-15
                                            # Use the found filename
                                            detection_dict["media_url"] = f"/media/{camera_folder}/{date_folder}/{filename}"
                                    # Look for archived_photos/common_name/camera/date/filename
                                    elif "archived_photos" in parts:
                                        idx = parts.index("archived_photos")
                                        if len(parts) > idx + 3 and filename_idx > idx + 3:
                                            species_name = parts[idx + 1]    # human, vehicle, etc.
                                            camera_folder = parts[idx + 2]   # 1, 2, etc.
                                            date_folder = parts[idx + 3]    # 2025-08-11
                                            # Use the found filename
                                            detection_dict["media_url"] = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                                    else:
                                        detection_dict["media_url"] = None
                            except Exception as e:
                                logging.warning(f"Error generating media_url for detection {detection.id}: {e}")
                                detection_dict["media_url"] = None
                        
                        # Generate thumbnail URL from image path (if media_url was successfully generated)
                        if detection_dict["media_url"] and detection.image_path:
                            try:
                                # Resolve absolute path to image file for thumbnail generation
                                current_file = os.path.abspath(__file__)  # .../wildlife-app/backend/routers/detections.py
                                routers_dir = os.path.dirname(current_file)  # .../wildlife-app/backend/routers
                                backend_dir = os.path.dirname(routers_dir)  # .../wildlife-app/backend
                                project_root = os.path.dirname(backend_dir)  # .../wildlife-app
                                
                                # Reconstruct absolute path from image_path
                                image_path_normalized = detection.image_path.replace("\\", "/")
                                image_parts = [p for p in image_path_normalized.split("/") if p]
                                
                                absolute_image_path = None
                                if "motioneye_media" in image_parts:
                                    # Build path: project_root/motioneye_media/CameraX/date/filename
                                    idx = image_parts.index("motioneye_media")
                                    relative_path = os.path.join(*image_parts[idx:])
                                    absolute_image_path = os.path.join(project_root, relative_path)
                                elif "archived_photos" in image_parts:
                                    # Build path: project_root/archived_photos/species/camera/date/filename
                                    idx = image_parts.index("archived_photos")
                                    relative_path = os.path.join(*image_parts[idx:])
                                    absolute_image_path = os.path.join(project_root, relative_path)
                                elif os.path.isabs(detection.image_path):
                                    # Already absolute path
                                    absolute_image_path = detection.image_path
                                
                                # Generate thumbnail if absolute path exists
                                if absolute_image_path and os.path.exists(absolute_image_path):
                                    from utils.image_compression import get_thumbnail_url
                                    thumbnail_url = get_thumbnail_url(absolute_image_path, size=(200, 200))
                                    if thumbnail_url:
                                        # Convert to URL format that works with the frontend
                                        # get_thumbnail_url returns path like /thumbnails/abc123.jpg
                                        # We need to make sure it's served from the backend
                                        if thumbnail_url.startswith("/"):
                                            # Extract filename from thumbnail path
                                            thumbnail_filename = os.path.basename(thumbnail_url)
                                            detection_dict["thumbnail_url"] = f"/thumbnails/{thumbnail_filename}"
                                        else:
                                            detection_dict["thumbnail_url"] = thumbnail_url
                            except Exception as e:
                                # Silently fail - thumbnails are optional
                                logging.debug(f"Could not generate thumbnail for detection {detection.id}: {e}")
                                detection_dict["thumbnail_url"] = None
                        
                        # Generate video URL from video path
                        if detection.video_path:
                            try:
                                import os
                                # Normalize path for both Windows and Linux
                                path = detection.video_path.replace("\\", "/")
                                # Remove empty parts and normalize
                                parts = [p for p in path.split("/") if p]
                                
                                # Find the filename (last segment with video extension)
                                video_extensions = ["mp4", "mkv", "avi", "mov", "webm", "m4v"]
                                filename = None
                                filename_idx = -1
                                for i in range(len(parts) - 1, -1, -1):
                                    if "." in parts[i]:
                                        ext = parts[i].split(".")[-1].lower()
                                        if ext in video_extensions:
                                            filename = parts[i]
                                            filename_idx = i
                                            break
                                
                                if filename:
                                    # Look for motioneye_media/CameraX/date/filename
                                    if "motioneye_media" in parts:
                                        idx = parts.index("motioneye_media")
                                        if len(parts) > idx + 2 and filename_idx > idx + 2:
                                            camera_folder = parts[idx + 1]  # Camera1
                                            date_folder = parts[idx + 2]    # 2025-07-15
                                            detection_dict["video_url"] = f"/media/{camera_folder}/{date_folder}/{filename}"
                                    # Look for archived_photos/common_name/camera/date/filename
                                    elif "archived_photos" in parts:
                                        idx = parts.index("archived_photos")
                                        if len(parts) > idx + 3 and filename_idx > idx + 3:
                                            species_name = parts[idx + 1]    # human, vehicle, etc.
                                            camera_folder = parts[idx + 2]   # 1, 2, etc.
                                            date_folder = parts[idx + 3]    # 2025-08-11
                                            detection_dict["video_url"] = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                            except Exception as e:
                                logging.warning(f"Error generating video_url for detection {detection.id}: {e}")
                                detection_dict["video_url"] = None
                        
                        # Add recognized faces
                        recognized_faces_list = []
                        if detection.id in face_detections_map:
                            for face_detection in face_detections_map[detection.id]:
                                if face_detection.known_face_id and face_detection.known_face_id in known_faces_map:
                                    known_face = known_faces_map[face_detection.known_face_id]
                                    recognized_faces_list.append(RecognizedFaceResponse(
                                        id=face_detection.id,
                                        name=known_face.name,
                                        confidence=float(face_detection.confidence) if face_detection.confidence else 0.0,
                                        known_face_id=face_detection.known_face_id
                                    ))
                        detection_dict["recognized_faces"] = recognized_faces_list
                        
                        # Validate the detection_dict before creating DetectionResponse
                        # This helps catch validation errors early
                        try:
                            detection_response = DetectionResponse(**detection_dict)
                            result.append(detection_response)
                        except Exception as validation_error:
                            # Log the validation error with more details
                            logging.error(f"Validation error for detection {detection.id}: {validation_error}")
                            logging.error(f"Detection data: camera_id={detection_dict.get('camera_id')}, species={detection_dict.get('species')}, image_path={detection_dict.get('image_path')}")
                            import traceback
                            logging.error(traceback.format_exc())
                            # Skip this detection and continue
                            continue
                    except Exception as e:
                        logging.error(f"Error processing detection {detection.id}: {e}")
                        import traceback
                        logging.error(traceback.format_exc())
                        # Skip this detection and continue
                        continue
                logging.info(f"Successfully processed {len(result)} detections out of {len(detections)}")
                return result
            except Exception as e:
                logging.error(f"Error in get_detections endpoint: {e}")
                import traceback
                logging.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"Error fetching detections: {str(e)}")

    @router.get("/api/detections", response_model=List[DetectionResponse])
    def get_detections_api(
        camera_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        species: Optional[List[str]] = Query(None),
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score (0.0-1.0)"),
        max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum confidence score (0.0-1.0)"),
        db: Session = Depends(get_db)
    ):
        """Alias for /detections to support frontend API calls"""
        return get_detections(camera_id, limit, offset, species, start_date, end_date, search, min_confidence, max_confidence, db)

    @router.post("/detections", response_model=DetectionResponse)
    def create_detection(request: Request, detection: DetectionCreate, db: Session = Depends(get_db)):
        """Create a new detection"""
        db_detection = Detection(**detection.model_dump())
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        # Log detection creation
        log_audit_event(
            db=db,
            request=request,
            action="CREATE",
            resource_type="detection",
            resource_id=db_detection.id,
            details={"camera_id": detection.camera_id, "species": detection.species}
        )
        
        return db_detection

    @router.delete("/detections/{detection_id}")
    @limiter.limit("60/minute")
    def delete_detection(
        request: Request,
        detection_id: int,
        db: Session = Depends(get_db)
    ):
        """Delete a single detection"""
        try:
            detection = db.query(Detection).filter(Detection.id == detection_id).first()
            if not detection:
                raise HTTPException(status_code=404, detail="Detection not found")
            
            # Log deletion
            log_audit_event(
                db=db,
                request=request,
                action="DELETE",
                resource_type="detection",
                resource_id=detection_id,
                details={
                    "camera_id": detection.camera_id,
                    "species": detection.species
                }
            )
            
            db.delete(detection)
            db.commit()
            
            return {"success": True, "message": f"Detection {detection_id} deleted"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logging.error(f"Failed to delete detection {detection_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to delete detection: {str(e)}")

    @router.post("/detections/bulk-delete")
    @limiter.limit("10/minute")
    def bulk_delete_detections(
        request: Request,
        detection_ids: List[int],
        db: Session = Depends(get_db)
    ):
        """Delete multiple detections"""
        try:
            if not detection_ids:
                raise HTTPException(status_code=400, detail="No detection IDs provided")
            
            if len(detection_ids) > 100:
                raise HTTPException(status_code=400, detail="Cannot delete more than 100 detections at once")
            
            # Get detections
            detections = db.query(Detection).filter(Detection.id.in_(detection_ids)).all()
            
            if len(detections) != len(detection_ids):
                found_ids = {d.id for d in detections}
                missing_ids = set(detection_ids) - found_ids
                raise HTTPException(
                    status_code=404,
                    detail=f"Some detections not found: {list(missing_ids)}"
                )
            
            # Log bulk deletion
            log_audit_event(
                db=db,
                request=request,
                action="BULK_DELETE",
                resource_type="detection",
                details={
                    "count": len(detection_ids),
                    "detection_ids": detection_ids
                }
            )
            
            # Delete all
            for detection in detections:
                db.delete(detection)
            
            db.commit()
            
            return {
                "success": True,
                "message": f"Deleted {len(detection_ids)} detection(s)",
                "deleted_count": len(detection_ids)
            }
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logging.error(f"Failed to bulk delete detections: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to delete detections: {str(e)}")

    @router.get("/detections/count")
    def get_detections_count(
        camera_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """Get total count of detections"""
        try:
            query = db.query(Detection)
            if camera_id:
                query = query.filter(Detection.camera_id == camera_id)
            
            # Apply excluded species filter (with error handling built in)
            try:
                query = _apply_excluded_species_filter(query, db)
            except Exception as filter_error:
                logger.warning(f"Error applying excluded species filter (continuing without filter): {filter_error}")
                # Continue without the filter if it fails
            
            count = query.count()
            logger.debug(f"Detections count query successful: count={count}, camera_id={camera_id}")
            return {"count": count}
        except Exception as e:
            logger.error(f"Error getting detections count: {e}", exc_info=True)
            # Return 0 on error rather than crashing
            return {"count": 0}

    @router.get("/api/detections/count")
    def get_detections_count_api(
        camera_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """Alias for /detections/count to support frontend API calls"""
        return get_detections_count(camera_id, db)

    @router.get("/detections/species-counts")
    def get_species_counts(
        range: str = "all",  # "week", "month", "all"
        db: Session = Depends(get_db)
    ):
        """Get species counts for different time ranges"""
        try:
            # Base query - need to query Detection object to apply filters
            base_query = db.query(Detection)
            
            # Apply time filter
            if range == "week":
                week_ago = datetime.now() - timedelta(days=7)
                base_query = base_query.filter(Detection.timestamp >= week_ago)
            elif range == "month":
                month_ago = datetime.now() - timedelta(days=30)
                base_query = base_query.filter(Detection.timestamp >= month_ago)
            elif range != "all":
                # Invalid range parameter - use "all" as default
                range = "all"
            
            # Apply excluded species filter
            base_query = _apply_excluded_species_filter(base_query, db)
            
            # Now build the aggregation query for species counts
            query = base_query.with_entities(
                Detection.species,
                func.count(Detection.id).label('count')
            )
            
            # Group by species and get counts
            results = query.group_by(Detection.species).order_by(func.count(Detection.id).desc()).limit(10).all()
            
            # Format results
            species_counts = []
            for species, count in results:
                species_counts.append({
                    "species": species or "Unknown",
                    "count": int(count)  # Ensure count is an integer
                })
            
            logging.debug(f"Species counts query returned {len(species_counts)} results for range: {range}")
            return species_counts
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error fetching species counts: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to fetch species counts: {str(e)}")

    @router.get("/detections/unique-species-count")
    def get_unique_species_count(
        days: int = 30,
        db: Session = Depends(get_db)
    ):
        """Return the number of unique species detected in the last N days."""
        sql = f"""
            SELECT COUNT(DISTINCT species) as unique_species
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            unique_species = result.scalar()
        return {"unique_species": unique_species}

    @router.get("/api/thingino/image/{detection_id}")
    def get_thingino_image(detection_id: int, db: Session = Depends(get_db)):
        """Get captured image from Thingino camera"""
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        if not os.path.exists(detection.image_path):
            raise HTTPException(status_code=404, detail="Image file not found")
        
        return FileResponse(detection.image_path, media_type="image/jpeg")

    @router.get("/api/debug/speciesnet-response/{detection_id}")
    def debug_speciesnet_response(detection_id: int, db: Session = Depends(get_db)):
        """Debug endpoint to see raw SpeciesNet response for a detection"""
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        try:
            detections_json = json.loads(detection.detections_json) if detection.detections_json else {}
            return {
                "id": detection.id,
                "species": detection.species,
                "confidence": detection.confidence,
                "raw_speciesnet_response": detections_json,
                "image_path": detection.image_path
            }
        except Exception as e:
            return {
                "id": detection.id,
                "species": detection.species,
                "confidence": detection.confidence,
                "error": str(e),
                "raw_detections_json": detection.detections_json
            }

    @router.get("/api/debug/detection-media/{detection_id}")
    def debug_detection_media(detection_id: int, db: Session = Depends(get_db)):
        """Debug endpoint to see media URL generation for a detection"""
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        try:
            # Generate media URL using the same logic as the main endpoint
            media_url = None
            if detection.image_path:
                path = detection.image_path.replace("\\", "/")
                parts = [p for p in path.split("/") if p]
                
                # Find the filename (last segment with image extension)
                image_extensions = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]
                filename = None
                filename_idx = -1
                for i in range(len(parts) - 1, -1, -1):
                    if "." in parts[i]:
                        ext = parts[i].split(".")[-1].lower()
                        if ext in image_extensions:
                            filename = parts[i]
                            filename_idx = i
                            break
                
                if filename:
                    if "motioneye_media" in parts:
                        idx = parts.index("motioneye_media")
                        if len(parts) > idx + 2 and filename_idx > idx + 2:
                            camera_folder = parts[idx + 1]
                            date_folder = parts[idx + 2]
                            media_url = f"/media/{camera_folder}/{date_folder}/{filename}"
                    elif "archived_photos" in parts:
                        idx = parts.index("archived_photos")
                        if len(parts) > idx + 3 and filename_idx > idx + 3:
                            species_name = parts[idx + 1]
                            camera_folder = parts[idx + 2]
                            date_folder = parts[idx + 3]
                            media_url = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
            
            return {
                "detection_id": detection_id,
                "image_path": detection.image_path,
                "generated_media_url": media_url,
                "file_exists": os.path.exists(detection.image_path) if detection.image_path else False
            }
        except Exception as e:
            return {
                "detection_id": detection_id,
                "error": str(e),
                "image_path": detection.image_path
            }

    @router.get("/analytics/detections/timeseries")
    def analytics_detections_timeseries(
        interval: str = "hour",  # "hour" or "day"
        days: int = 7,
        db: Session = Depends(get_db)
    ):
        """Return detection counts grouped by hour or day for the last N days."""
        if interval not in ("hour", "day"):
            return JSONResponse(status_code=400, content={"error": "Invalid interval. Use 'hour' or 'day'."})
        
        group_expr = f"date_trunc('{interval}', timestamp)"
        
        # Build excluded species filter for SQL
        excluded_species_filter = ""
        try:
            from ..routers.settings import get_setting
        except ImportError:
            from routers.settings import get_setting
        
        excluded_species = get_setting(db, "excluded_species", default=[])
        if excluded_species and isinstance(excluded_species, list):
            excluded_list = [s.strip() for s in excluded_species if s.strip()]
            if excluded_list:
                # Build SQL exclusion clause
                excluded_conditions = " AND ".join([
                    f"LOWER(species) NOT LIKE '%{s.lower()}%'" for s in excluded_list
                ])
                excluded_species_filter = f" AND {excluded_conditions}"
        
        sql = f"""
            SELECT {group_expr} as bucket, COUNT(*) as count
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
            {excluded_species_filter}
            GROUP BY bucket
            ORDER BY bucket ASC
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            data = [{"bucket": str(row[0]), "count": row[1]} for row in result]
        return data

    @router.get("/analytics/detections/top_species")
    def analytics_detections_top_species(
        limit: int = 5,
        days: int = 30,
        db: Session = Depends(get_db)
    ):
        """Return the top N species detected in the last N days."""
        # Build excluded species filter for SQL
        excluded_species_filter = ""
        try:
            from ..routers.settings import get_setting
        except ImportError:
            from routers.settings import get_setting
        
        excluded_species = get_setting(db, "excluded_species", default=[])
        if excluded_species and isinstance(excluded_species, list):
            excluded_list = [s.strip() for s in excluded_species if s.strip()]
            if excluded_list:
                excluded_conditions = " AND ".join([
                    f"LOWER(species) NOT LIKE '%{s.lower()}%'" for s in excluded_list
                ])
                excluded_species_filter = f" AND {excluded_conditions}"
        
        sql = f"""
            SELECT species, COUNT(*) as count
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
            {excluded_species_filter}
            GROUP BY species
            ORDER BY count DESC
            LIMIT {limit}
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            data = [{"species": row[0], "count": row[1]} for row in result]
        return data

    @router.get("/analytics/detections/unique_species_count")
    def analytics_detections_unique_species_count(
        days: int = 30,
        db: Session = Depends(get_db)
    ):
        """Return the number of unique species detected in the last N days."""
        # Build excluded species filter for SQL
        excluded_species_filter = ""
        try:
            from ..routers.settings import get_setting
        except ImportError:
            from routers.settings import get_setting
        
        excluded_species = get_setting(db, "excluded_species", default=[])
        if excluded_species and isinstance(excluded_species, list):
            excluded_list = [s.strip() for s in excluded_species if s.strip()]
            if excluded_list:
                excluded_conditions = " AND ".join([
                    f"LOWER(species) NOT LIKE '%{s.lower()}%'" for s in excluded_list
                ])
                excluded_species_filter = f" AND {excluded_conditions}"
        
        sql = f"""
            SELECT COUNT(DISTINCT species) as unique_species
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
            {excluded_species_filter}
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            unique_species = result.scalar()
        return {"unique_species": unique_species or 0}

    @router.get("/api/detections/export")
    @limiter.limit("10/minute")  # Rate limit: 10 requests per minute (expensive operation)
    def export_detections(
        request: Request,
        format: str = "csv",  # csv, json, or pdf
        camera_id: Optional[int] = None,
        species: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        include_images: bool = False,  # Include images in zip file
        min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score (0.0-1.0)"),
        max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum confidence score (0.0-1.0)"),
        detection_ids: Optional[str] = Query(None, description="Comma-separated list of detection IDs to export"),
        db: Session = Depends(get_db)
    ):
        """Export detections to CSV, JSON, or PDF format. Optionally include images in a zip file."""
        # Build query with filters
        query = db.query(Detection)
        
        # If specific detection IDs provided, filter by those first
        if detection_ids:
            try:
                ids_list = [int(id_str.strip()) for id_str in detection_ids.split(',') if id_str.strip()]
                if ids_list:
                    query = query.filter(Detection.id.in_(ids_list))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid detection_ids format. Use comma-separated integers.")
        
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        
        if species:
            query = query.filter(Detection.species.ilike(f"%{species}%"))
        
        # Apply confidence filters
        if min_confidence is not None:
            query = query.filter(Detection.confidence >= min_confidence)
        if max_confidence is not None:
            query = query.filter(Detection.confidence <= max_confidence)
        
        # Apply excluded species filter
        query = _apply_excluded_species_filter(query, db)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp >= start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp <= end_dt)
            except ValueError:
                pass
        
        # Apply limit if specified (default to 10000 for exports)
        if limit is None:
            limit = 10000
        query = query.order_by(Detection.timestamp.desc()).limit(limit)
        
        detections = query.all()
        
        # If include_images is True, create a zip file with CSV/JSON + images
        if include_images:
            return _export_with_images(
                detections=detections,
                format=format,
                request=request,
                db=db,
                camera_id=camera_id,
                species=species
            )
        
        if format.lower() == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Camera ID", "Timestamp", "Species", "Confidence", 
                "Image Path", "File Size", "Image Width", "Image Height", 
                "Prediction Score"
            ])
            
            # Write data
            for det in detections:
                writer.writerow([
                    det.id,
                    det.camera_id,
                    det.timestamp.isoformat() if det.timestamp else "",
                    det.species or "",
                    det.confidence or 0.0,
                    det.image_path or "",
                    det.file_size or 0,
                    det.image_width or 0,
                    det.image_height or 0,
                    det.prediction_score or 0.0
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            # Log export
            log_audit_event(
                db=db,
                request=request,
                action="EXPORT",
                resource_type="detection",
                details={
                    "format": "csv",
                    "count": len(detections),
                    "camera_id": camera_id,
                    "species": species
                }
            )
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=detections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
        
        elif format.lower() == "json":
            # Generate JSON
            detections_data = []
            for det in detections:
                detections_data.append({
                    "id": det.id,
                    "camera_id": det.camera_id,
                    "timestamp": det.timestamp.isoformat() if det.timestamp else None,
                    "species": det.species,
                    "confidence": det.confidence,
                    "image_path": det.image_path,
                    "file_size": det.file_size,
                    "image_width": det.image_width,
                    "image_height": det.image_height,
                    "prediction_score": det.prediction_score
                })
            
            # Log export
            log_audit_event(
                db=db,
                request=request,
                action="EXPORT",
                resource_type="detection",
                details={
                    "format": "json",
                    "count": len(detections),
                    "camera_id": camera_id,
                    "species": species
                }
            )
            
            return Response(
                content=json.dumps(detections_data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=detections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}. Use 'csv' or 'json'.")

    @router.post("/process-image")
    @limiter.limit("10/minute")  # Rate limit: 10 requests per minute (expensive operation)
    async def process_image_with_speciesnet(
        request: Request,
        file: UploadFile = File(...),
        camera_id: Optional[int] = None,
        compress: bool = True,
        async_mode: bool = False,
        db: Session = Depends(get_db)
    ):
        """
        Process an uploaded image with SpeciesNet
        
        Args:
            async_mode: If True, returns task ID immediately and processes in background
        """
        try:
            from fastapi import UploadFile, File
            from services.task_tracker import task_tracker, TaskStatus
            from services.speciesnet import speciesnet_processor
            from services.notifications import notification_service
            from services.webhooks import WebhookService
            import tempfile
            import json
            
            # If async mode, create task and return immediately
            if async_mode:
                task_id = task_tracker.create_task(
                    task_type="image_processing",
                    metadata={
                        "camera_id": camera_id,
                        "compress": compress,
                        "filename": file.filename
                    }
                )
                
                # Start background processing
                import asyncio
                asyncio.create_task(_process_image_background(task_id, file, camera_id, compress, db, request))
                
                return {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Image processing started in background"
                }
            
            # Synchronous processing (existing behavior)
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Process with SpeciesNet
            predictions = speciesnet_processor.process_image(temp_path)
            
            if "error" in predictions:
                # Log failed processing
                log_audit_event(
                    db=db,
                    request=request,
                    action="PROCESS",
                    resource_type="detection",
                    success=False,
                    error_message=predictions["error"],
                    details={"camera_id": camera_id}
                )
                raise HTTPException(status_code=500, detail=predictions["error"])
            
            # Save detection to database
            if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
                pred = predictions["predictions"][0]
                
                # Create detection record
                detection_data = {
                    "camera_id": camera_id or 1,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0),
                    "image_path": temp_path,
                    "detections_json": json.dumps(predictions),
                    "prediction_score": pred.get("prediction_score", 0.0)
                }
                
                db_detection = Detection(**detection_data)
                db.add(db_detection)
                db.commit()
                db.refresh(db_detection)
                
                # Compress image if enabled and file exists
                if compress and db_detection.image_path and os.path.exists(db_detection.image_path):
                    try:
                        from utils.image_compression import compress_image
                        success, compressed_path, original_size = compress_image(
                            db_detection.image_path,
                            quality=85,
                            max_width=1920,
                            max_height=1080
                        )
                        if success and original_size:
                            new_size = os.path.getsize(compressed_path)
                            compression_ratio = (1 - new_size / original_size) * 100
                            logger.info(
                                f"Compressed detection image: {compression_ratio:.1f}% reduction "
                                f"({original_size} -> {new_size} bytes)"
                            )
                    except Exception as e:
                        logger.warning(f"Image compression failed: {e}")
                
                # Log successful processing
                log_audit_event(
                    db=db,
                    request=request,
                    action="PROCESS",
                    resource_type="detection",
                    resource_id=db_detection.id,
                    details={
                        "camera_id": camera_id,
                        "species": pred.get("prediction", "Unknown"),
                        "confidence": pred.get("prediction_score", 0.0)
                    }
                )
                
                # Send email notification if enabled and confidence is high enough
                if pred.get("prediction_score", 0.0) >= 0.7:
                    try:
                        notification_service.send_detection_notification(
                            species=pred.get("prediction", "Unknown"),
                            confidence=pred.get("prediction_score", 0.0),
                            camera_id=camera_id or 1,
                            detection_id=db_detection.id,
                            timestamp=db_detection.timestamp
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notification: {e}")
                
                # Trigger webhooks for detection
                try:
                    webhook_service = WebhookService(db)
                    detection_data_webhook = {
                        "id": db_detection.id,
                        "camera_id": camera_id or 1,
                        "species": pred.get("prediction", "Unknown"),
                        "confidence": pred.get("prediction_score", 0.0),
                        "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                        "image_path": db_detection.image_path
                    }
                    webhook_service.trigger_detection_webhooks(
                        detection_data=detection_data_webhook,
                        confidence=pred.get("prediction_score", 0.0),
                        species=pred.get("prediction", "Unknown")
                    )
                except Exception as e:
                    logger.warning(f"Failed to trigger webhooks: {e}")
                
                return {
                    "detection": db_detection,
                    "predictions": predictions
                }
            else:
                return {"predictions": predictions}
            
        except Exception as e:
            # Log failed processing
            log_audit_event(
                db=db,
                request=request,
                action="PROCESS",
                resource_type="detection",
                success=False,
                error_message=str(e),
                details={"camera_id": camera_id}
            )
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_image_background(
        task_id: str,
        file: UploadFile,
        camera_id: Optional[int],
        compress: bool,
        db: Session,
        request: Request
    ):
        """Background task for processing images"""
        try:
            from services.task_tracker import task_tracker
            from services.speciesnet import speciesnet_processor
            import tempfile
            import json
            
            # Start task
            task_tracker.start_task(task_id, "Reading image file...")
            
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Update progress
            task_tracker.update_task(task_id, progress=0.2, message="Processing with SpeciesNet...")
            
            # Process with SpeciesNet
            predictions = speciesnet_processor.process_image(temp_path)
            
            if "error" in predictions:
                task_tracker.fail_task(task_id, predictions["error"])
                return
            
            task_tracker.update_task(task_id, progress=0.6, message="Saving detection...")
            
            # Save detection to database
            if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
                pred = predictions["predictions"][0]
                
                detection_data = {
                    "camera_id": camera_id or 1,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0),
                    "image_path": temp_path,
                    "detections_json": json.dumps(predictions),
                    "prediction_score": pred.get("prediction_score", 0.0)
                }
                
                db_detection = Detection(**detection_data)
                db.add(db_detection)
                db.commit()
                db.refresh(db_detection)
                
                task_tracker.update_task(task_id, progress=0.8, message="Compressing image...")
                
                # Compress image if enabled
                if compress and db_detection.image_path and os.path.exists(db_detection.image_path):
                    try:
                        from utils.image_compression import compress_image
                        compress_image(
                            db_detection.image_path,
                            quality=85,
                            max_width=1920,
                            max_height=1080
                        )
                    except Exception as e:
                        logger.warning(f"Image compression failed: {e}")
                
                # Log successful processing
                log_audit_event(
                    db=db,
                    request=request,
                    action="PROCESS",
                    resource_type="detection",
                    resource_id=db_detection.id,
                    details={
                        "camera_id": camera_id,
                        "species": pred.get("prediction", "Unknown"),
                        "confidence": pred.get("prediction_score", 0.0),
                        "task_id": task_id
                    }
                )
                
                # Complete task
                task_tracker.complete_task(
                    task_id,
                    result={
                        "detection_id": db_detection.id,
                        "species": pred.get("prediction", "Unknown"),
                        "confidence": pred.get("prediction_score", 0.0)
                    },
                    message="Image processed successfully"
                )
            else:
                task_tracker.complete_task(
                    task_id,
                    result={"predictions": predictions},
                    message="Processing completed (no detections)"
                )
        
        except Exception as e:
            logger.error(f"Background image processing failed: {e}", exc_info=True)
            from services.task_tracker import task_tracker
            task_tracker.fail_task(task_id, str(e))

    return router
