"""Camera management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Body
from slowapi import Limiter
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
import requests
import os
import tempfile
import json
from datetime import datetime

try:
    from ..database import SessionLocal, Camera, Detection
    from ..models import CameraResponse, CameraCreate
    from ..services.motioneye import motioneye_client
    from ..camera_sync import sync_motioneye_cameras
    from ..utils.caching import get_cached, set_cached, clear_cache
    from ..utils.audit import log_audit_event
    from ..config import MOTIONEYE_URL
except ImportError:
    from database import SessionLocal, Camera, Detection
    from models import CameraResponse, CameraCreate
    from services.motioneye import motioneye_client
    from camera_sync import sync_motioneye_cameras
    from utils.caching import get_cached, set_cached, clear_cache
    from utils.audit import log_audit_event
    from config import MOTIONEYE_URL

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_cameras_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup cameras router with rate limiting and dependencies"""
    
    @router.get("/cameras", response_model=List[CameraResponse])
    @limiter.limit("120/minute")
    def get_cameras(request: Request, response: Response, db: Session = Depends(get_db)):
        """Get list of all cameras"""
        # Explicitly set CORS headers
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        try:
            cached = get_cached("cameras_list", ttl=60)
            if cached:
                # Ensure cached data is a list
                if isinstance(cached, list):
                    logger.info(f"Returning {len(cached)} cameras from cache")
                    return cached
                else:
                    logger.warning(f"Cache contains non-list data: {type(cached)}, clearing cache")
                    clear_cache("cameras_list")
            
            try:
                cameras = db.query(Camera).all()
                logger.info(f"Found {len(cameras)} cameras in database")
            except Exception as query_error:
                logger.error(f"Camera query failed: {query_error}", exc_info=True)
                # Return empty list on query error
                return []
            
            if not cameras:
                logger.info("No cameras found in database")
                return []
            
            camera_ids = [camera.id for camera in cameras]
            
            # Get detection counts for all cameras at once
            detection_counts = {}
            if camera_ids:
                from sqlalchemy import func
                counts_query = db.query(
                    Detection.camera_id,
                    func.count(Detection.id).label('count')
                ).filter(Detection.camera_id.in_(camera_ids)).group_by(Detection.camera_id).all()
                detection_counts = {camera_id: count for camera_id, count in counts_query}
            
            # Get last detection timestamps
            last_detections = {}
            if camera_ids:
                from sqlalchemy import func
                subquery = db.query(
                    Detection.camera_id,
                    func.max(Detection.timestamp).label('max_timestamp')
                ).filter(Detection.camera_id.in_(camera_ids)).group_by(Detection.camera_id).subquery()
                
                last_detections_query = db.query(Detection).join(
                    subquery,
                    (Detection.camera_id == subquery.c.camera_id) & 
                    (Detection.timestamp == subquery.c.max_timestamp)
                ).all()
                last_detections = {det.camera_id: det.timestamp.isoformat() for det in last_detections_query}
            
            result = []
            logger.info(f"Processing {len(cameras)} cameras from database")
            processed_count = 0
            error_count = 0
            for camera in cameras:
                try:
                    processed_count += 1
                    logger.debug(f"Processing camera {camera.id} ({processed_count}/{len(cameras)}): {camera.name}")
                    detection_count = detection_counts.get(camera.id, 0)
                    last_detection_time = last_detections.get(camera.id)
                    status = "active" if (camera.is_active if camera.is_active is not None else True) else "inactive"
                    
                    camera_name = str(camera.name).strip() if camera.name and str(camera.name).strip() else "Unnamed Camera"
                    camera_url = str(camera.url).strip() if camera.url and str(camera.url).strip() else "rtsp://localhost"
                    
                    # Safely get location fields (may not exist if migration hasn't run)
                    # Use getattr with default None to avoid AttributeError
                    latitude_val = getattr(camera, 'latitude', None)
                    longitude_val = getattr(camera, 'longitude', None)
                    address_val = getattr(camera, 'address', None)
                    # Geofence fields
                    geofence_enabled_val = getattr(camera, 'geofence_enabled', False)
                    geofence_type_val = getattr(camera, 'geofence_type', None)
                    geofence_data_val = None
                    geofence_data_str = getattr(camera, 'geofence_data', None)
                    if geofence_data_str:
                        try:
                            geofence_data_val = json.loads(geofence_data_str) if isinstance(geofence_data_str, str) else geofence_data_str
                        except:
                            geofence_data_val = None
                    
                    width_val = max(320, min(7680, int(camera.width) if camera.width is not None else 1280))
                    height_val = max(240, min(4320, int(camera.height) if camera.height is not None else 720))
                    framerate_val = max(1, min(120, int(camera.framerate) if camera.framerate is not None else 30))
                    stream_port_val = max(1024, min(65535, int(camera.stream_port) if camera.stream_port is not None else 8081))
                    stream_quality_val = max(1, min(100, int(camera.stream_quality) if camera.stream_quality is not None else 100))
                    stream_maxrate_val = max(1, min(120, int(camera.stream_maxrate) if camera.stream_maxrate is not None else 30))
                    detection_threshold_val = max(0, min(100000, int(camera.detection_threshold) if camera.detection_threshold is not None else 1500))
                    detection_smart_mask_speed_val = max(0, min(100, int(camera.detection_smart_mask_speed) if camera.detection_smart_mask_speed is not None else 10))
                    movie_quality_val = max(1, min(100, int(camera.movie_quality) if camera.movie_quality is not None else 100))
                    snapshot_interval_val = max(0, min(3600, int(camera.snapshot_interval) if camera.snapshot_interval is not None else 0))
                    
                    movie_codec_val = "mkv"
                    if camera.movie_codec:
                        codec = str(camera.movie_codec).strip()
                        if ':' in codec:
                            codec = codec.split(':')[0]
                        movie_codec_val = codec[:50] if len(codec) > 50 else codec
                    
                    target_dir_val = str(camera.target_dir).strip() if camera.target_dir and str(camera.target_dir).strip() else "./motioneye_media"
                    
                    camera_dict = {
                        "id": camera.id,
                        "name": camera_name,
                        "url": camera_url,
                        "is_active": camera.is_active if camera.is_active is not None else True,
                        "width": width_val,
                        "height": height_val,
                        "framerate": framerate_val,
                        "stream_port": stream_port_val,
                        "stream_quality": stream_quality_val,
                        "stream_maxrate": stream_maxrate_val,
                        "stream_localhost": camera.stream_localhost if camera.stream_localhost is not None else False,
                        "detection_enabled": camera.detection_enabled if camera.detection_enabled is not None else True,
                        "detection_threshold": detection_threshold_val,
                        "detection_smart_mask_speed": detection_smart_mask_speed_val,
                        "movie_output": camera.movie_output if camera.movie_output is not None else True,
                        "movie_quality": movie_quality_val,
                        "movie_codec": movie_codec_val,
                        "snapshot_interval": snapshot_interval_val,
                        "target_dir": target_dir_val,
                        "created_at": camera.created_at if camera.created_at else datetime.utcnow(),
                        "stream_url": motioneye_client.get_camera_stream_url(camera.id) if camera.id else None,
                        "mjpeg_url": motioneye_client.get_camera_mjpeg_url(camera.id) if camera.id else None,
                        "detection_count": detection_count,
                        "last_detection": last_detection_time,
                        "status": status,
                        "location": None,
                        "latitude": latitude_val,
                        "longitude": longitude_val,
                        "address": address_val,
                        "geofence_enabled": geofence_enabled_val if geofence_enabled_val is not None else False,
                        "geofence_type": geofence_type_val,
                        "geofence_data": geofence_data_val,
                    }
                    
                    try:
                        camera_response = CameraResponse(**camera_dict)
                        result.append(camera_response)
                        logger.debug(f"Successfully added camera {camera.id} to result (total: {len(result)})")
                    except Exception as validation_error:
                        error_count += 1
                        logger.error(f"Validation error for camera {camera.id} ({camera_name}): {validation_error}", exc_info=True)
                        logger.error(f"Camera dict that failed: {camera_dict}")
                        # Try to return basic camera info even if validation fails
                        try:
                            # Create a minimal valid response
                            minimal_dict = {
                                "id": camera.id,
                                "name": camera_name,
                                "url": camera_url,
                                "is_active": True,
                                "width": 1280,
                                "height": 720,
                                "framerate": 30,
                                "stream_port": 8081,
                                "stream_quality": 100,
                                "stream_maxrate": 30,
                                "stream_localhost": False,
                                "detection_enabled": True,
                                "detection_threshold": 1500,
                                "detection_smart_mask_speed": 10,
                                "movie_output": True,
                                "movie_quality": 100,
                                "movie_codec": "mkv",
                                "snapshot_interval": 0,
                                "target_dir": "./motioneye_media",
                                "created_at": camera.created_at or datetime.utcnow(),
                                "latitude": None,
                                "longitude": None,
                                "address": None,
                            }
                            camera_response = CameraResponse(**minimal_dict)
                            result.append(camera_response)
                            logger.warning(f"Camera {camera.id} returned with minimal data due to validation error")
                        except Exception as fallback_error:
                            logger.error(f"Failed to create fallback response for camera {camera.id}: {fallback_error}")
                            continue
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing camera {camera.id} ({camera.name if hasattr(camera, 'name') else 'unknown'}): {e}", exc_info=True)
                    continue
            
            # Convert Pydantic models to dicts for caching (AFTER processing all cameras)
            try:
                cached_result = [camera.model_dump() if hasattr(camera, 'model_dump') else dict(camera) for camera in result]
                set_cached("cameras_list", cached_result, ttl=60)
            except Exception as cache_error:
                logger.warning(f"Failed to cache cameras list: {cache_error}")
            
            logger.info(f"Successfully processed {len(result)} cameras out of {len(cameras)} total")
            logger.info(f"Processed: {processed_count}, Errors: {error_count}, Result count: {len(result)}")
            if len(result) < len(cameras):
                skipped = len(cameras) - len(result)
                logger.warning(f"{skipped} cameras were skipped due to errors - check logs above for details")
                logger.warning(f"Expected {len(cameras)} cameras but only {len(result)} were returned!")
            
            return result
        except Exception as e:
            logger.error(f"Error in get_cameras: {e}", exc_info=True)
            import traceback
            logger.error(traceback.format_exc())
            # Return empty list on any error to prevent frontend crashes
            return []
    
    @router.get("/api/cameras", response_model=List[CameraResponse])
    @limiter.limit("120/minute")
    def get_cameras_api(request: Request, response: Response, db: Session = Depends(get_db)):
        """Alias for /cameras to support frontend API calls"""
        # Explicitly set CORS headers
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return get_cameras(request, response, db)
    

    
    @router.options("/cameras/sync")
    def sync_cameras_from_motioneye_options(request: Request, response: Response):
        """Handle CORS preflight for camera sync endpoint"""
        # Explicitly set CORS headers to ensure browsers accept the request
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, Accept, Origin, X-Requested-With"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return {"message": "OK"}

    @router.post("/cameras/sync")
    @limiter.limit("10/minute")
    def sync_cameras_from_motioneye(request: Request, response: Response, db: Session = Depends(get_db)):
        """
        Synchronise cameras from MotionEye
        """
        # Explicitly set CORS headers for the actual request too
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"

        # Clear cameras cache before syncing to ensure fresh data
        try:
            from utils.caching import clear_cache
            clear_cache("cameras_list")
            logger.info("Cleared cameras cache before sync")
        except Exception as cache_clear_error:
            logger.warning(f"Failed to clear cameras cache: {cache_clear_error}")

        try:
            try:
                motioneye_check = requests.get(f"{MOTIONEYE_URL}/config/list", timeout=5)
                if motioneye_check.status_code != 200:
                    raise HTTPException(
                        status_code=503,
                        detail=f"MotionEye is not accessible (status {motioneye_check.status_code}). Please ensure MotionEye is running at {MOTIONEYE_URL}"
                    )
            except requests.exceptions.Timeout:
                raise HTTPException(
                    status_code=503,
                    detail=f"MotionEye connection timeout. Please ensure MotionEye is running at {MOTIONEYE_URL}"
                )
            except requests.exceptions.ConnectionError:
                raise HTTPException(
                    status_code=503,
                    detail=f"Cannot connect to MotionEye at {MOTIONEYE_URL}. Please ensure MotionEye is running."
                )
            except Exception as e:
                logger.warning(f"MotionEye connectivity check failed: {e}")
            
            result = sync_motioneye_cameras(db, motioneye_client, Camera)
            
            # Clear cameras cache after sync to ensure fresh data on next request
            try:
                from utils.caching import clear_cache
                clear_cache("cameras_list")
                logger.info("Cleared cameras cache after sync")
            except Exception as cache_clear_error:
                logger.warning(f"Failed to clear cameras cache after sync: {cache_clear_error}")
            
            log_audit_event(
                db=db,
                request=request,
                action="SYNC",
                resource_type="camera",
                details={
                    "synced": result.get("synced", 0),
                    "updated": result.get("updated", 0),
                    "removed": result.get("removed", 0)
                }
            )
            return result
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            log_audit_event(
                db=db,
                request=request,
                action="SYNC",
                resource_type="camera",
                success=False,
                error_message=str(e)
            )
            raise HTTPException(status_code=500, detail=f"Error syncing cameras: {str(e)}")
    
    @router.post("/cameras", response_model=CameraResponse)
    @limiter.limit("20/minute")
    def add_camera(request: Request, camera: CameraCreate, db: Session = Depends(get_db)):
        """Add a new camera"""
        camera_data = camera.model_dump()
        # Convert geofence_data from Dict to JSON string for database storage
        if 'geofence_data' in camera_data and camera_data['geofence_data'] is not None:
            camera_data['geofence_data'] = json.dumps(camera_data['geofence_data'])
        db_camera = Camera(**camera_data)
        db.add(db_camera)
        db.commit()
        db.refresh(db_camera)
        
        motioneye_config = {
            "name": camera.name,
            "netcam_url": camera.url,
            "width": camera.width,
            "height": camera.height,
            "framerate": camera.framerate,
            "stream_quality": camera.stream_quality,
            "stream_maxrate": camera.stream_maxrate,
            "stream_localhost": camera.stream_localhost,
            "motion_detection": camera.detection_enabled,
            "motion_threshold": camera.detection_threshold,
            "motion_smart_mask_speed": camera.detection_smart_mask_speed,
            "movie_output": camera.movie_output,
            "movie_quality": camera.movie_quality,
            "movie_codec": camera.movie_codec,
            "snapshot_interval": camera.snapshot_interval,
            "target_dir": camera.target_dir
        }
        
        success = motioneye_client.add_camera(motioneye_config)
        if not success:
            db.delete(db_camera)
            db.commit()
            log_audit_event(
                db=db,
                request=request,
                action="CREATE",
                resource_type="camera",
                success=False,
                error_message="Failed to add camera to MotionEye",
                details={"camera_name": camera.name}
            )
            raise HTTPException(status_code=500, detail="Failed to add camera to MotionEye")
        
        db_camera.stream_url = motioneye_client.get_camera_stream_url(db_camera.id)
        db_camera.mjpeg_url = motioneye_client.get_camera_mjpeg_url(db_camera.id)
        
        log_audit_event(
            db=db,
            request=request,
            action="CREATE",
            resource_type="camera",
            resource_id=db_camera.id,
            details={"camera_name": camera.name, "url": camera.url}
        )
        
        return db_camera
    
    @router.get("/cameras/{camera_id}")
    def get_camera(camera_id: int, db: Session = Depends(get_db)):
        """Get details for a specific camera"""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        return camera
    
    @router.get("/cameras/{camera_id}/motion-settings")
    def get_motion_settings(camera_id: int):
        """Get motion detection settings for a camera"""
        try:
            settings = motioneye_client.get_camera_config(camera_id)
            return {
                "camera_id": camera_id,
                "motion_detection": settings.get("motion_detection", True),
                "motion_threshold": settings.get("motion_threshold", 1500),
                "motion_smart_mask_speed": settings.get("motion_smart_mask_speed", 10)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get motion settings: {str(e)}")
    
    @router.post("/cameras/{camera_id}/motion-settings")
    @limiter.limit("20/minute")
    def update_motion_settings(request: Request, camera_id: int, settings, db: Session = Depends(get_db)):
        """Update motion detection settings"""
        try:
            from models import MotionSettings
            motioneye_config = {
                "motion_detection": settings.detection_enabled,
                "motion_threshold": settings.detection_threshold,
                "motion_smart_mask_speed": settings.detection_smart_mask_speed
            }
            success = motioneye_client.update_camera_config(camera_id, motioneye_config)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update motion settings")
            
            # Update database
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            if camera:
                camera.detection_enabled = settings.detection_enabled
                camera.detection_threshold = settings.detection_threshold
                camera.detection_smart_mask_speed = settings.detection_smart_mask_speed
                db.commit()
            
            log_audit_event(
                db=db,
                request=request,
                action="UPDATE",
                resource_type="camera",
                resource_id=camera_id,
                details={"motion_settings": motioneye_config}
            )
            return {"success": True, "message": "Motion settings updated"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update motion settings: {str(e)}")
    
    @router.get("/cameras/{camera_id}/geofence")
    @limiter.limit("60/minute")
    def get_camera_geofence(request: Request, camera_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
        """Get geofence settings for a camera"""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        geofence_enabled = getattr(camera, 'geofence_enabled', False) or False
        geofence_type = getattr(camera, 'geofence_type', None)
        geofence_data = None
        geofence_data_str = getattr(camera, 'geofence_data', None)
        if geofence_data_str:
            try:
                geofence_data = json.loads(geofence_data_str) if isinstance(geofence_data_str, str) else geofence_data_str
            except:
                geofence_data = None
        
        return {
            "camera_id": camera_id,
            "enabled": geofence_enabled,
            "type": geofence_type,
            "data": geofence_data
        }
    
    @router.post("/cameras/{camera_id}/geofence")
    @limiter.limit("20/minute")
    def update_camera_geofence(
        request: Request,
        camera_id: int,
        enabled: bool = Body(...),
        geofence_type: Optional[str] = Body(None),
        geofence_data: Optional[Dict[str, Any]] = Body(None),
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Update geofence settings for a camera"""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        # Validate geofence_type if provided
        if geofence_type and geofence_type not in ["polygon", "circle", "bounds"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid geofence_type. Must be one of: polygon, circle, bounds"
            )
        
        # Validate geofence_data if provided
        if enabled and geofence_type and geofence_data:
            if geofence_type == "polygon":
                if not isinstance(geofence_data, list) or len(geofence_data) < 3:
                    raise HTTPException(
                        status_code=400,
                        detail="Polygon requires at least 3 points"
                    )
                for point in geofence_data:
                    if not isinstance(point, dict) or "latitude" not in point or "longitude" not in point:
                        raise HTTPException(
                            status_code=400,
                            detail="Each polygon point must have latitude and longitude"
                        )
            elif geofence_type == "circle":
                required = ["latitude", "longitude", "radius_km"]
                for key in required:
                    if key not in geofence_data:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Circle requires: {', '.join(required)}"
                        )
            elif geofence_type == "bounds":
                required = ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
                for key in required:
                    if key not in geofence_data:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Bounds requires: {', '.join(required)}"
                        )
        
        # Update camera geofence settings
        camera.geofence_enabled = enabled
        if geofence_type:
            camera.geofence_type = geofence_type
        if geofence_data is not None:
            camera.geofence_data = json.dumps(geofence_data) if geofence_data else None
        elif not enabled:
            # Clear geofence data if disabled
            camera.geofence_type = None
            camera.geofence_data = None
        
        db.commit()
        db.refresh(camera)
        
        log_audit_event(
            db=db,
            request=request,
            action="UPDATE",
            resource_type="camera",
            resource_id=camera_id,
            details={
                "geofence_enabled": enabled,
                "geofence_type": geofence_type
            }
        )
        
        return {
            "success": True,
            "message": "Camera geofence settings updated",
            "enabled": enabled,
            "type": geofence_type,
            "data": geofence_data
        }
    
    @router.get("/stream/{camera_id}")
    def get_camera_stream(camera_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
        """Get camera stream information"""
        # Explicitly set CORS headers
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return {
            "camera_id": camera_id,
            "camera_name": camera.name,
            "rtsp_url": camera.url,
            "stream_url": motioneye_client.get_camera_stream_url(camera_id),
            "mjpeg_url": motioneye_client.get_camera_mjpeg_url(camera_id),
            "motioneye_url": MOTIONEYE_URL,
            "camera_type": "motioneye"
        }
    
    @router.post("/api/thingino/capture")
    async def capture_thingino_image(request: Request, camera_id: int, db: Session = Depends(get_db)):
        """Capture an image from the Thingino camera and process it"""
        try:
            from ..config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD
            from ..services.speciesnet import speciesnet_processor
            from ..services.notifications import notification_service
            from ..services.webhooks import WebhookService
            from ..services.events import get_event_manager
            from ..database import Detection
            import requests
            import tempfile
            import json
            from datetime import datetime
        except ImportError:
            from config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD
            from services.speciesnet import speciesnet_processor
            from services.notifications import notification_service
            from services.webhooks import WebhookService
            from services.events import get_event_manager
            from database import Detection
            import requests
            import tempfile
            import json
            from datetime import datetime
        
        try:
            # Get camera information
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            if not camera:
                raise HTTPException(status_code=404, detail="Camera not found")
            
            if camera_id not in [9, 10]:
                raise HTTPException(status_code=400, detail="This endpoint is only for Thingino cameras")
            
            # Download image from Thingino camera
            try:
                # Try to get image from camera with authentication for Thingino cameras
                auth = None
                if camera_id in [9, 10]:  # Thingino cameras
                    auth = (THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD)
                
                response = requests.get(camera.url, auth=auth, timeout=10)
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Failed to capture image: HTTP {response.status_code}")
                
                # Save image temporarily
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"thingino_capture_{timestamp}.jpg"
                temp_path = os.path.join(tempfile.gettempdir(), filename)
                
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                # Process with SpeciesNet
                predictions = speciesnet_processor.process_image(temp_path)
                
                if "error" in predictions:
                    raise HTTPException(status_code=500, detail=predictions["error"])
                
                # Extract species prediction
                species = "Unknown"
                confidence = 0.0
                
                if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
                    pred = predictions["predictions"][0]
                    species = pred.get("prediction", "Unknown")
                    confidence = pred.get("prediction_score", 0.0)
                
                # Save detection to database
                detection_data = {
                    "camera_id": camera_id,
                    "timestamp": datetime.now(),
                    "species": species,
                    "confidence": confidence,
                    "image_path": temp_path,
                    "detections_json": json.dumps(predictions),
                    "prediction_score": confidence
                }
                
                db_detection = Detection(**detection_data)
                db.add(db_detection)
                db.commit()
                db.refresh(db_detection)
                
                # Compress image if it exists
                if db_detection.image_path and os.path.exists(db_detection.image_path):
                    try:
                        from utils.image_compression import compress_image
                        success, compressed_path, original_size = compress_image(
                            db_detection.image_path,
                            quality=85,
                            max_width=1920,
                            max_height=1080
                        )
                        if success:
                            logger.info(f"Compressed captured image: {db_detection.image_path}")
                    except Exception as e:
                        logger.warning(f"Image compression failed: {e}")
                
                # Log successful capture
                log_audit_event(
                    db=db,
                    request=request,
                    action="CAPTURE",
                    resource_type="detection",
                    resource_id=db_detection.id,
                    details={
                        "camera_id": camera_id,
                        "camera_name": camera.name,
                        "species": species,
                        "confidence": confidence
                    }
                )
                
                # Send email notification if enabled and confidence is high enough
                if confidence >= 0.7:  # Only notify for high-confidence detections
                    try:
                        notification_service.send_detection_notification(
                            species=species,
                            confidence=confidence,
                            camera_id=camera_id,
                            camera_name=camera.name,
                            detection_id=db_detection.id,
                            image_url=f"/api/thingino/image/{db_detection.id}",
                            timestamp=db_detection.timestamp
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notification: {e}")
                
                # Trigger webhooks for detection
                try:
                    webhook_service = WebhookService(db)
                    detection_data_webhook = {
                        "id": db_detection.id,
                        "camera_id": camera_id,
                        "camera_name": camera.name,
                        "species": species,
                        "confidence": confidence,
                        "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                        "image_url": f"/api/thingino/image/{db_detection.id}"
                    }
                    webhook_service.trigger_detection_webhooks(
                        detection_data=detection_data_webhook,
                        confidence=confidence,
                        species=species
                    )
                except Exception as e:
                    logger.warning(f"Failed to trigger webhooks: {e}")
                
                # Broadcast the new detection to connected clients
                event_manager = get_event_manager()
                detection_event = {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "species": species,
                    "confidence": confidence,
                    "image_path": temp_path,
                    "timestamp": db_detection.timestamp.isoformat(),
                    "media_url": f"/api/thingino/image/{db_detection.id}"
                }
                await event_manager.broadcast_detection(detection_event)
                
                return {
                    "status": "success",
                    "detection_id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "species": species,
                    "confidence": confidence,
                    "predictions": predictions
                }
                
            except requests.exceptions.RequestException as e:
                # Log failed capture
                log_audit_event(
                    db=db,
                    request=request,
                    action="CAPTURE",
                    resource_type="detection",
                    success=False,
                    error_message=f"Failed to connect to camera: {str(e)}",
                    details={"camera_id": camera_id}
                )
                raise HTTPException(status_code=500, detail=f"Failed to connect to camera: {str(e)}")
            
        except Exception as e:
            # Log failed capture
            log_audit_event(
                db=db,
                request=request,
                action="CAPTURE",
                resource_type="detection",
                success=False,
                error_message=str(e),
                details={"camera_id": camera_id}
            )
            raise HTTPException(status_code=500, detail=str(e))
    
    return router

