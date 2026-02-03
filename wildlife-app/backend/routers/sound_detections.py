"""Sound detection management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json
import os

try:
    from ..database import get_db, SoundDetection, Camera, Detection
    from ..models import SoundDetectionResponse, SoundDetectionCreate
except ImportError:
    from database import get_db, SoundDetection, Camera, Detection
    from models import SoundDetectionResponse, SoundDetectionCreate

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_sound_detections_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup sound detections router with rate limiting and dependencies"""
    
    @router.get("/api/sound-detections", response_model=List[SoundDetectionResponse])
    @limiter.limit("120/minute")
    def get_sound_detections(
        request: Request,
        camera_id: Optional[int] = None,
        detection_id: Optional[int] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sound_class: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Get sound detections with optional filtering and pagination"""
        try:
            query = db.query(SoundDetection)
            
            # Apply filters
            if camera_id:
                query = query.filter(SoundDetection.camera_id == camera_id)
            if detection_id:
                query = query.filter(SoundDetection.detection_id == detection_id)
            if sound_class:
                query = query.filter(SoundDetection.sound_class.ilike(f"%{sound_class}%"))
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(SoundDetection.timestamp >= start_dt)
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}")
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(SoundDetection.timestamp <= end_dt)
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}")
            
            # Order by timestamp descending (most recent first)
            query = query.order_by(SoundDetection.timestamp.desc())
            
            # Apply pagination
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            
            sound_detections = query.all()
            
            # Batch fetch cameras and detections for efficiency
            camera_ids = {sd.camera_id for sd in sound_detections if sd.camera_id}
            detection_ids = {sd.detection_id for sd in sound_detections if sd.detection_id}
            
            cameras = {}
            if camera_ids:
                cameras_query = db.query(Camera).filter(Camera.id.in_(camera_ids))
                cameras = {c.id: c for c in cameras_query.all()}
            
            detections = {}
            if detection_ids:
                detections_query = db.query(Detection).filter(Detection.id.in_(detection_ids))
                detections = {d.id: d for d in detections_query.all()}
            
            # Convert to response models
            result = []
            for sd in sound_detections:
                try:
                    # Get camera name
                    camera_name = None
                    if sd.camera_id and sd.camera_id in cameras:
                        camera_name = cameras[sd.camera_id].name
                    
                    # Get detection species if linked
                    detection_species = None
                    if sd.detection_id and sd.detection_id in detections:
                        detection_species = detections[sd.detection_id].species
                    
                    # Generate audio URL
                    audio_url = None
                    if sd.audio_path:
                        audio_url = _generate_audio_url(sd.audio_path)
                    
                    # Parse audio_features if it's a JSON string
                    audio_features = None
                    if sd.audio_features:
                        try:
                            if isinstance(sd.audio_features, str):
                                audio_features = json.loads(sd.audio_features)
                            else:
                                audio_features = sd.audio_features
                        except (json.JSONDecodeError, TypeError):
                            audio_features = None
                    
                    result.append(SoundDetectionResponse(
                        id=sd.id,
                        camera_id=sd.camera_id,
                        detection_id=sd.detection_id,
                        sound_class=sd.sound_class,
                        confidence=float(sd.confidence) if sd.confidence else 0.0,
                        audio_path=sd.audio_path,
                        duration=float(sd.duration) if sd.duration else None,
                        audio_features=audio_features,
                        timestamp=sd.timestamp,
                        audio_url=audio_url,
                        camera_name=camera_name,
                        detection_species=detection_species
                    ))
                except Exception as e:
                    logger.error(f"Error processing sound detection {sd.id}: {e}", exc_info=True)
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting sound detections: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving sound detections: {str(e)}")
    
    @router.get("/api/sound-detections/count")
    @limiter.limit("120/minute")
    def get_sound_detections_count(
        request: Request,
        camera_id: Optional[int] = None,
        detection_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sound_class: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Get total count of sound detections matching filters (for pagination)"""
        try:
            query = db.query(func.count(SoundDetection.id))
            
            # Apply same filters as get_sound_detections
            if camera_id:
                query = query.filter(SoundDetection.camera_id == camera_id)
            if detection_id:
                query = query.filter(SoundDetection.detection_id == detection_id)
            if sound_class:
                query = query.filter(SoundDetection.sound_class.ilike(f"%{sound_class}%"))
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(SoundDetection.timestamp >= start_dt)
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}")
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(SoundDetection.timestamp <= end_dt)
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}")
            
            count = query.scalar() or 0
            return {"count": count}
            
        except Exception as e:
            logger.error(f"Error getting sound detections count: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving sound detections count: {str(e)}")
    
    @router.get("/api/sound-detections/{sound_detection_id}", response_model=SoundDetectionResponse)
    @limiter.limit("120/minute")
    def get_sound_detection(
        request: Request,
        sound_detection_id: int,
        db: Session = Depends(get_db)
    ):
        """Get a specific sound detection by ID"""
        try:
            sd = db.query(SoundDetection).filter(SoundDetection.id == sound_detection_id).first()
            if not sd:
                raise HTTPException(status_code=404, detail=f"Sound detection {sound_detection_id} not found")
            
            # Get camera name
            camera_name = None
            if sd.camera_id:
                camera = db.query(Camera).filter(Camera.id == sd.camera_id).first()
                if camera:
                    camera_name = camera.name
            
            # Get detection species if linked
            detection_species = None
            if sd.detection_id:
                detection = db.query(Detection).filter(Detection.id == sd.detection_id).first()
                if detection:
                    detection_species = detection.species
            
            # Generate audio URL
            audio_url = None
            if sd.audio_path:
                audio_url = _generate_audio_url(sd.audio_path)
            
            # Parse audio_features if it's a JSON string
            audio_features = None
            if sd.audio_features:
                try:
                    if isinstance(sd.audio_features, str):
                        audio_features = json.loads(sd.audio_features)
                    else:
                        audio_features = sd.audio_features
                except (json.JSONDecodeError, TypeError):
                    audio_features = None
            
            return SoundDetectionResponse(
                id=sd.id,
                camera_id=sd.camera_id,
                detection_id=sd.detection_id,
                sound_class=sd.sound_class,
                confidence=float(sd.confidence) if sd.confidence else 0.0,
                audio_path=sd.audio_path,
                duration=float(sd.duration) if sd.duration else None,
                audio_features=audio_features,
                timestamp=sd.timestamp,
                audio_url=audio_url,
                camera_name=camera_name,
                detection_species=detection_species
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting sound detection {sound_detection_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving sound detection: {str(e)}")
    
    @router.post("/api/sound-detections", response_model=SoundDetectionResponse)
    @limiter.limit("60/minute")
    def create_sound_detection(
        request: Request,
        sound_detection: SoundDetectionCreate,
        db: Session = Depends(get_db)
    ):
        """Create a new sound detection"""
        try:
            # Validate camera_id if provided
            if sound_detection.camera_id:
                camera = db.query(Camera).filter(Camera.id == sound_detection.camera_id).first()
                if not camera:
                    raise HTTPException(status_code=404, detail=f"Camera {sound_detection.camera_id} not found")
            
            # Validate detection_id if provided
            if sound_detection.detection_id:
                detection = db.query(Detection).filter(Detection.id == sound_detection.detection_id).first()
                if not detection:
                    raise HTTPException(status_code=404, detail=f"Detection {sound_detection.detection_id} not found")
            
            # Convert audio_features dict to JSON string if provided
            audio_features_str = None
            if sound_detection.audio_features:
                try:
                    audio_features_str = json.dumps(sound_detection.audio_features)
                except (TypeError, ValueError):
                    logger.warning(f"Could not serialize audio_features to JSON: {sound_detection.audio_features}")
            
            # Create sound detection
            db_sound_detection = SoundDetection(
                camera_id=sound_detection.camera_id,
                detection_id=sound_detection.detection_id,
                sound_class=sound_detection.sound_class,
                confidence=sound_detection.confidence,
                audio_path=sound_detection.audio_path,
                duration=sound_detection.duration,
                audio_features=audio_features_str
            )
            
            db.add(db_sound_detection)
            db.commit()
            db.refresh(db_sound_detection)
            
            # Get camera name and detection species for response
            camera_name = None
            if db_sound_detection.camera_id:
                camera = db.query(Camera).filter(Camera.id == db_sound_detection.camera_id).first()
                if camera:
                    camera_name = camera.name
            
            detection_species = None
            if db_sound_detection.detection_id:
                detection = db.query(Detection).filter(Detection.id == db_sound_detection.detection_id).first()
                if detection:
                    detection_species = detection.species
            
            # Generate audio URL
            audio_url = None
            if db_sound_detection.audio_path:
                audio_url = _generate_audio_url(db_sound_detection.audio_path)
            
            return SoundDetectionResponse(
                id=db_sound_detection.id,
                camera_id=db_sound_detection.camera_id,
                detection_id=db_sound_detection.detection_id,
                sound_class=db_sound_detection.sound_class,
                confidence=float(db_sound_detection.confidence) if db_sound_detection.confidence else 0.0,
                audio_path=db_sound_detection.audio_path,
                duration=float(db_sound_detection.duration) if db_sound_detection.duration else None,
                audio_features=sound_detection.audio_features,
                timestamp=db_sound_detection.timestamp,
                audio_url=audio_url,
                camera_name=camera_name,
                detection_species=detection_species
            )
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating sound detection: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error creating sound detection: {str(e)}")
    
    @router.delete("/api/sound-detections/{sound_detection_id}")
    @limiter.limit("60/minute")
    def delete_sound_detection(
        request: Request,
        sound_detection_id: int,
        db: Session = Depends(get_db)
    ):
        """Delete a sound detection"""
        try:
            sd = db.query(SoundDetection).filter(SoundDetection.id == sound_detection_id).first()
            if not sd:
                raise HTTPException(status_code=404, detail=f"Sound detection {sound_detection_id} not found")
            
            db.delete(sd)
            db.commit()
            
            return {"message": f"Sound detection {sound_detection_id} deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting sound detection {sound_detection_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error deleting sound detection: {str(e)}")
    
    return router


def _generate_audio_url(audio_path: str) -> Optional[str]:
    """Generate URL for audio file (similar to media URL generation for images/videos)"""
    if not audio_path:
        return None
    
    try:
        # Normalize path
        path = audio_path.replace("\\", "/")
        parts = [p for p in path.split("/") if p]
        
        # Find the filename
        audio_extensions = ["wav", "mp3", "flac", "ogg", "m4a", "aac"]
        filename = None
        filename_idx = -1
        for i in range(len(parts) - 1, -1, -1):
            if "." in parts[i]:
                ext = parts[i].split(".")[-1].lower()
                if ext in audio_extensions:
                    filename = parts[i]
                    filename_idx = i
                    break
        
        if not filename:
            return None
        
        # Look for motioneye_media/CameraX/date/filename pattern
        if "motioneye_media" in parts:
            idx = parts.index("motioneye_media")
            if len(parts) > idx + 2 and filename_idx > idx + 2:
                camera_folder = parts[idx + 1]
                date_folder = parts[idx + 2]
                # Return URL in format: /media/{camera}/{date}/{filename}
                return f"/media/{camera_folder}/{date_folder}/{filename}"
        
        # If no standard pattern found, return a generic URL
        # For now, we'll use the media endpoint (which may need to be extended to handle audio)
        return f"/media/audio/{filename}"
        
    except Exception as e:
        logger.warning(f"Error generating audio URL for {audio_path}: {e}")
        return None
