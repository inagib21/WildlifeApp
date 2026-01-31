"""Face recognition API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import os
import logging
import json
import numpy as np

try:
    from ..database import get_db, KnownFace, FaceDetection, Detection
    from ..services.face_recognition import face_recognition_service
except (ImportError, ValueError):
    from database import get_db, KnownFace, FaceDetection, Detection
    from services.face_recognition import face_recognition_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/faces")
async def list_known_faces(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all known faces"""
    faces = db.query(KnownFace).filter(KnownFace.is_active == True).all()
    return [
        {
            "id": face.id,
            "name": face.name,
            "image_path": face.image_path,
            "is_active": face.is_active,
            "created_at": face.created_at.isoformat() if face.created_at else None,
            "updated_at": face.updated_at.isoformat() if face.updated_at else None,
            "notes": face.notes,
            "tolerance": face.tolerance if face.tolerance is not None else 0.6
        }
        for face in faces
    ]


@router.get("/api/faces/{face_id}")
async def get_known_face(face_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific known face"""
    face = db.query(KnownFace).filter(KnownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail=f"Face with ID {face_id} not found")
    
    return {
        "id": face.id,
        "name": face.name,
        "image_path": face.image_path,
        "is_active": face.is_active,
        "created_at": face.created_at.isoformat() if face.created_at else None,
        "updated_at": face.updated_at.isoformat() if face.updated_at else None,
        "notes": face.notes,
        "tolerance": face.tolerance if face.tolerance is not None else 0.6
    }


@router.post("/api/faces")
async def add_known_face(
    name: str = Form(...),
    image: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    tolerance: Optional[float] = Form(0.6),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Add a new known face from uploaded image"""
    logger.info(f"Received request to add known face: name={name}, filename={image.filename if image else 'None'}, content_type={image.content_type if image else 'None'}")
    
    if not face_recognition_service.is_available():
        logger.error("Face recognition service not available")
        raise HTTPException(status_code=503, detail="Face recognition service not available")
    
    # Validate image file first
    if not image.filename:
        logger.error("No filename provided in upload")
        raise HTTPException(status_code=400, detail="Image filename is required")
    
    # Check file extension - support common image formats that face_recognition can handle
    allowed_extensions = {
        '.jpg', '.jpeg',  # JPEG
        '.png',           # PNG
        '.bmp',           # BMP
        '.gif',           # GIF
        '.webp',          # WebP (modern format)
        '.tiff', '.tif',  # TIFF
        '.ico',           # ICO (icon format)
        '.heic', '.heif'  # HEIC/HEIF (Apple format, if supported)
    }
    file_ext = os.path.splitext(image.filename)[1].lower()
    if file_ext not in allowed_extensions:
        logger.error(f"Unsupported file extension: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format: {file_ext}. Allowed formats: JPG, JPEG, PNG, BMP, GIF, WebP, TIFF, ICO, HEIC"
        )
    
    # Save uploaded image temporarily
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await image.read()
            if not content or len(content) == 0:
                logger.error("Empty file uploaded")
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
            tmp_file.write(content)
            tmp_path = tmp_file.name
            logger.info(f"Saved uploaded image to temporary file: {tmp_path} (size: {len(content)} bytes)")
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing uploaded file: {str(e)}")
    
    try:
        # Add face using the service - Run in thread pool to prevent blocking
        logger.info(f"Attempting to detect and add face from {tmp_path}")
        
        # This is a blocking operation that can take time, so we offload it to a thread
        import asyncio
        import functools
        
        loop = asyncio.get_event_loop()
        # Use partial to pass arguments to the synchronous method
        face_id = await loop.run_in_executor(
            None, 
            functools.partial(
                face_recognition_service.add_known_face, 
                db, 
                name, 
                tmp_path, 
                notes,
                tolerance if tolerance is not None else 0.6
            )
        )
        
        if not face_id:
            logger.warning(f"No face detected in image: {tmp_path}")
            raise HTTPException(
                status_code=400,
                detail=(
                    "No face detected in image. Please ensure: "
                    "The image contains a clear, front-facing face. "
                    "The face is well-lit and not too small. "
                    "The face is not obscured or at an extreme angle. "
                    "The image format is supported (JPG, PNG, etc.)"
                )
            )
        
        face = db.query(KnownFace).filter(KnownFace.id == face_id).first()
        return {
            "id": face.id,
            "name": face.name,
            "image_path": face.image_path,
            "is_active": face.is_active,
            "created_at": face.created_at.isoformat() if face.created_at else None,
            "updated_at": face.updated_at.isoformat() if face.updated_at else None,
            "notes": face.notes,
            "tolerance": face.tolerance if face.tolerance is not None else 0.6,
            "message": f"Successfully added known face: {name}"
        }
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {tmp_path}: {e}")


@router.delete("/api/faces/{face_id}")
async def delete_known_face(face_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete (deactivate) a known face"""
    face = db.query(KnownFace).filter(KnownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail=f"Face with ID {face_id} not found")
    
    # Soft delete - mark as inactive
    face.is_active = False
    db.commit()
    
    # Remove from cache
    if face_id in face_recognition_service.known_faces:
        del face_recognition_service.known_faces[face_id]
    if face_id in face_recognition_service.known_face_names:
        del face_recognition_service.known_face_names[face_id]
    
    return {"message": f"Face '{face.name}' deactivated successfully"}


@router.put("/api/faces/{face_id}")
async def update_known_face(
    face_id: int,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    tolerance: Optional[float] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update a known face's name, notes, or tolerance"""
    face = db.query(KnownFace).filter(KnownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail=f"Face with ID {face_id} not found")
    
    if name:
        face.name = name
        # Update cache
        if face_id in face_recognition_service.known_face_names:
            face_recognition_service.known_face_names[face_id] = name
    
    if notes is not None:
        face.notes = notes
    
    if tolerance is not None:
        if not (0.0 <= tolerance <= 1.0):
            raise HTTPException(status_code=400, detail="Tolerance must be between 0.0 and 1.0")
        face.tolerance = tolerance
        # Update cache
        if face_id in face_recognition_service.known_face_tolerance:
            face_recognition_service.known_face_tolerance[face_id] = tolerance
    
    db.commit()
    db.refresh(face)
    
    return {
        "id": face.id,
        "name": face.name,
        "notes": face.notes,
        "tolerance": face.tolerance if face.tolerance is not None else 0.6,
        "message": "Face updated successfully"
    }


@router.get("/api/detections/{detection_id}/faces")
async def get_detection_faces(detection_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get face detections for a specific detection"""
    face_detections = db.query(FaceDetection).filter(
        FaceDetection.detection_id == detection_id
    ).all()
    
    results = []
    for fd in face_detections:
        known_face = None
        if fd.known_face_id:
            known_face = db.query(KnownFace).filter(KnownFace.id == fd.known_face_id).first()
        
        result = {
            "id": fd.id,
            "detection_id": fd.detection_id,
            "confidence": fd.confidence,
            "face_location": json.loads(fd.face_location) if fd.face_location else None,
            "created_at": fd.created_at.isoformat() if fd.created_at else None
        }
        
        if known_face:
            result["known_face"] = {
                "id": known_face.id,
                "name": known_face.name
            }
        else:
            result["known_face"] = None
            result["name"] = "Unknown"
        
        results.append(result)
    
    return results


@router.post("/api/faces/reload")
async def reload_known_faces(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Reload known faces from database into cache"""
    face_recognition_service.load_known_faces(db)
    return {
        "message": "Known faces reloaded",
        "count": len(face_recognition_service.known_faces)
    }


@router.get("/api/faces/stats")
async def get_face_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get statistics for known faces (recognition counts, etc.)"""
    try:
        # Get total known faces
        total_faces = db.query(KnownFace).filter(KnownFace.is_active == True).count()
        
        # Get recognition counts per face - convert face_id to string for JSON serialization
        recognition_counts = {}
        try:
            face_detections = db.query(
                FaceDetection.known_face_id,
                func.count(FaceDetection.id).label('count')
            ).filter(
                FaceDetection.known_face_id.isnot(None)
            ).group_by(FaceDetection.known_face_id).all()
            
            for face_id, count in face_detections:
                # Convert face_id to int to ensure it's JSON serializable
                recognition_counts[int(face_id)] = int(count)
        except Exception as e:
            logger.warning(f"Error getting recognition counts: {e}")
            recognition_counts = {}
        
        # Get total recognitions
        total_recognitions = 0
        try:
            total_recognitions = db.query(FaceDetection).filter(
                FaceDetection.known_face_id.isnot(None)
            ).count()
        except Exception as e:
            logger.warning(f"Error getting total recognitions: {e}")
        
        # Get recent recognitions (last 7 days)
        # Use timezone-aware datetime
        recent_recognitions = 0
        try:
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_recognitions = db.query(FaceDetection).filter(
                FaceDetection.known_face_id.isnot(None),
                FaceDetection.created_at >= seven_days_ago
            ).count()
        except Exception as e:
            logger.warning(f"Error getting recent recognitions: {e}")
        
        return {
            "total_faces": int(total_faces),
            "total_recognitions": int(total_recognitions),
            "recent_recognitions": int(recent_recognitions),
            "recognition_counts": recognition_counts
        }
    except Exception as e:
        logger.error(f"Error getting face stats: {e}", exc_info=True)
        # Return a valid response even on error
        return {
            "total_faces": 0,
            "total_recognitions": 0,
            "recent_recognitions": 0,
            "recognition_counts": {}
        }


@router.delete("/api/faces/batch")
async def bulk_delete_faces(
    face_ids: List[int] = Body(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Bulk delete (deactivate) multiple faces"""
    deleted_count = 0
    for face_id in face_ids:
        face = db.query(KnownFace).filter(KnownFace.id == face_id).first()
        if face:
            face.is_active = False
            # Remove from cache
            if face_id in face_recognition_service.known_faces:
                del face_recognition_service.known_faces[face_id]
            if face_id in face_recognition_service.known_face_names:
                del face_recognition_service.known_face_names[face_id]
            if face_id in face_recognition_service.known_face_tolerance:
                del face_recognition_service.known_face_tolerance[face_id]
            deleted_count += 1
    
    db.commit()
    return {
        "message": f"Deleted {deleted_count} face(s) successfully",
        "deleted_count": deleted_count
    }


@router.get("/api/faces/export")
async def export_faces(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Export all known faces data for backup"""
    faces = db.query(KnownFace).filter(KnownFace.is_active == True).all()
    
    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "faces": []
    }
    
    for face in faces:
        face_data = {
            "id": face.id,
            "name": face.name,
            "face_encoding": face.face_encoding,
            "image_path": face.image_path,
            "notes": face.notes,
            "tolerance": face.tolerance if face.tolerance is not None else 0.6,
            "created_at": face.created_at.isoformat() if face.created_at else None,
            "updated_at": face.updated_at.isoformat() if face.updated_at else None
        }
        export_data["faces"].append(face_data)
    
    return export_data


@router.post("/api/faces/import")
async def import_faces(
    export_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Import faces from exported data"""
    if not face_recognition_service.is_available():
        raise HTTPException(status_code=503, detail="Face recognition service not available")
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    faces_data = export_data.get("faces", [])
    
    for face_data in faces_data:
        try:
            # Check if face already exists by name
            existing = db.query(KnownFace).filter(
                KnownFace.name == face_data.get("name")
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # Create new face
            new_face = KnownFace(
                name=face_data.get("name"),
                face_encoding=face_data.get("face_encoding"),
                image_path=face_data.get("image_path"),
                notes=face_data.get("notes"),
                tolerance=face_data.get("tolerance", 0.6),
                is_active=True
            )
            db.add(new_face)
            db.flush()
            
            # Update cache
            try:
                encoding = json.loads(new_face.face_encoding)
                import numpy as np
                face_recognition_service.known_faces[new_face.id] = np.array(encoding)
                face_recognition_service.known_face_names[new_face.id] = new_face.name
                face_recognition_service.known_face_tolerance[new_face.id] = new_face.tolerance if new_face.tolerance else 0.6
            except Exception as e:
                logger.warning(f"Could not add face {new_face.name} to cache: {e}")
            
            imported_count += 1
        except Exception as e:
            errors.append(f"Error importing {face_data.get('name', 'unknown')}: {str(e)}")
    
    db.commit()
    
    return {
        "message": f"Imported {imported_count} face(s), skipped {skipped_count} duplicate(s)",
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors
    }
