"""Detection management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request, File, UploadFile
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
from fastapi.responses import Response, JSONResponse

try:
    from ..database import engine, Camera, Detection
    from ..models import DetectionResponse, DetectionCreate
    from ..utils.audit import log_audit_event
    from ..services.events import get_event_manager
except ImportError:
    from database import engine, Camera, Detection
    from models import DetectionResponse, DetectionCreate
    from utils.audit import log_audit_event
    from services.events import get_event_manager

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_detections_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup detections router with rate limiting and dependencies"""
    
    event_manager = get_event_manager()
    
    @router.get("/detections", response_model=List[DetectionResponse])
    def get_detections(
        camera_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        species: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
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
                
                if species is not None:
                    query = query.filter(Detection.species.ilike(f"%{species}%"))
                
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
                logging.info(f"Query returned {len(detections)} detections from database")
            
                # Batch-fetch all cameras to avoid N+1 queries
                camera_ids = {d.camera_id for d in detections if d.camera_id is not None}
                cameras = {}
                if camera_ids:
                    cameras = {c.id: c for c in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()}
            
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
                            "camera_name": str(camera_name)  # Add camera name to response
                        }
                
                        # Generate media URL from image path
                        if detection.image_path:
                            try:
                                # Normalize path for both Windows and Linux
                                path = detection.image_path.replace("\\", "/")
                                parts = path.split("/")
                                # Look for motioneye_media/CameraX/date/filename or archived_photos/common_name/camera/date/filename
                                if "motioneye_media" in parts:
                                    idx = parts.index("motioneye_media")
                                    if len(parts) > idx + 3:
                                        camera_folder = parts[idx + 1]  # Camera1
                                        date_folder = parts[idx + 2]    # 2025-07-15
                                        filename = parts[idx + 3]       # 11-00-07.jpg
                                        detection_dict["media_url"] = f"/media/{camera_folder}/{date_folder}/{filename}"
                                elif "archived_photos" in parts:
                                    idx = parts.index("archived_photos")
                                    if len(parts) > idx + 4:
                                        # archived_photos/common_name/camera/date/filename
                                        species_name = parts[idx + 1]    # human, vehicle, etc.
                                        camera_folder = parts[idx + 2]   # 1, 2, etc.
                                        date_folder = parts[idx + 3]    # 2025-08-11
                                        filename = parts[idx + 4]        # 13-08-44.jpg
                                        
                                        # Keep the original camera folder name (don't add "Camera" prefix)
                                        # This matches the actual file structure: archived_photos/human/2/2025-08-11/13-08-44.jpg
                                        detection_dict["media_url"] = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                            except Exception as e:
                                logging.warning(f"Error generating media_url for detection {detection.id}: {e}")
                                detection_dict["media_url"] = None
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
        species: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Alias for /detections to support frontend API calls"""
        return get_detections(camera_id, limit, offset, species, start_date, end_date, search, db)

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
        query = db.query(Detection)
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        count = query.count()
        return {"count": count}

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
            # Base query
            query = db.query(Detection.species, func.count(Detection.id).label('count'))
            
            # Apply time filter
            if range == "week":
                week_ago = datetime.now() - timedelta(days=7)
                query = query.filter(Detection.timestamp >= week_ago)
            elif range == "month":
                month_ago = datetime.now() - timedelta(days=30)
                query = query.filter(Detection.timestamp >= month_ago)
            elif range != "all":
                # Invalid range parameter
                raise HTTPException(status_code=400, detail=f"Invalid range parameter: {range}. Must be 'week', 'month', or 'all'")
            
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
                parts = path.split("/")
                
                if "motioneye_media" in parts:
                    idx = parts.index("motioneye_media")
                    if len(parts) > idx + 3:
                        camera_folder = parts[idx + 1]
                        date_folder = parts[idx + 2]
                        filename = parts[idx + 3]
                        media_url = f"/media/{camera_folder}/{date_folder}/{filename}"
                elif "archived_photos" in parts:
                    idx = parts.index("archived_photos")
                    if len(parts) > idx + 4:
                        species_name = parts[idx + 1]
                        camera_folder = parts[idx + 2]
                        date_folder = parts[idx + 3]
                        filename = parts[idx + 4]
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
        days: int = 7
    ):
        """Return detection counts grouped by hour or day for the last N days."""
        if interval not in ("hour", "day"):
            return JSONResponse(status_code=400, content={"error": "Invalid interval. Use 'hour' or 'day'."})
        
        group_expr = f"date_trunc('{interval}', timestamp)"
        
        sql = f"""
            SELECT {group_expr} as bucket, COUNT(*) as count
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
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
        days: int = 30
    ):
        """Return the top N species detected in the last N days."""
        sql = f"""
            SELECT species, COUNT(*) as count
            FROM detections
            WHERE timestamp >= NOW() - INTERVAL '{days} days'
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
        days: int = 30
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
        db: Session = Depends(get_db)
    ):
        """Export detections to CSV, JSON, or PDF format"""
        # Build query with filters
        query = db.query(Detection)
        
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        
        if species:
            query = query.filter(Detection.species.ilike(f"%{species}%"))
        
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
