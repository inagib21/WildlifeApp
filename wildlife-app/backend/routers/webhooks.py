"""Webhook management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import json
import os
import tempfile
import requests
import asyncio

try:
    from ..database import Camera, Detection, Webhook
    from ..models import WebhookCreate, WebhookResponse
    from ..utils.audit import log_audit_event
    from ..services.events import get_event_manager
    from ..services.speciesnet import speciesnet_processor
    from ..services.notifications import notification_service
    from ..services.webhooks import WebhookService
    from ..motioneye_webhook import parse_motioneye_payload
    from ..motioneye_events import should_process_event
    from ..config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD
except ImportError:
    from database import Camera, Detection, Webhook
    from models import WebhookCreate, WebhookResponse
    from utils.audit import log_audit_event
    from services.events import get_event_manager
    from services.speciesnet import speciesnet_processor
    from services.notifications import notification_service
    from services.webhooks import WebhookService
    from motioneye_webhook import parse_motioneye_payload
    from motioneye_events import should_process_event
    from config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_webhooks_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup webhooks router with rate limiting and dependencies"""
    
    event_manager = get_event_manager()
    
    @router.post("/api/thingino/webhook")
    async def thingino_webhook(request: Request, db: Session = Depends(get_db)):
        """Handle webhook notifications from Thingino camera for motion detection"""
        try:
            # Get the JSON data from Thingino
            data = await request.json()
            
            print(f"Thingino webhook received: {data}")
            
            # Thingino sends data with these typical fields:
            # - camera_id: ID of the camera (we'll determine from image_url)
            # - message: Motion detection message
            # - timestamp: When the event occurred
            # - image_url: URL to the captured image
            
            message = data.get("message", "Motion detected")
            timestamp = data.get("timestamp", datetime.now().isoformat())
            image_url = data.get("image_url", "http://192.168.88.93/x/preview.cgi")
            
            # Determine camera ID based on the image URL
            if "192.168.88.97" in image_url:
                camera_id = 10  # Thingino Camera 2
            else:
                camera_id = 9   # Thingino Camera 1 (default)
            
            print(f"Processing Thingino motion detection: {message}")
            
            # Process detection inline (will take a few seconds but ensures it completes)
            print(f"[THINGINO] Processing detection for camera {camera_id}, URL: {image_url}")
            
            try:
                # Use authentication for Thingino cameras
                auth = None
                if "192.168.88.93" in image_url or "192.168.88.97" in image_url:
                    auth = (THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD)
                
                response = requests.get(image_url, auth=auth, timeout=15)
                if response.status_code != 200:
                    print(f"Failed to download image from Thingino: HTTP {response.status_code}")
                    return {"status": "error", "message": f"Failed to download image: HTTP {response.status_code}"}
                
                # Save image temporarily
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"thingino_motion_{timestamp_str}.jpg"
                temp_path = os.path.join(tempfile.gettempdir(), filename)
                
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"Image saved to: {temp_path}")
                
                # Process with SpeciesNet
                predictions = speciesnet_processor.process_image(temp_path)
                
                if "error" in predictions:
                    print(f"SpeciesNet processing error: {predictions['error']}")
                    # Still save the detection, but mark as unprocessed
                    detection_data = {
                        "camera_id": camera_id,
                        "timestamp": datetime.now(),
                        "species": "Unknown",
                        "confidence": 0.0,
                        "image_path": temp_path,
                        "detections_json": json.dumps({"error": predictions["error"]}),
                        "prediction_score": 0.0
                    }
                else:
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
                
                # Create detection record
                try:
                    db_detection = Detection(**detection_data)
                    db.add(db_detection)
                    db.flush()  # Flush to get the ID without committing yet
                    logger.info(f"[Thingino] ✅ Detection created in database (ID: {db_detection.id}, Camera: {camera_id}, Species: {detection_data['species']}, Confidence: {detection_data['confidence']:.2f})")
                    
                    # Commit the detection
                    db.commit()
                    logger.info(f"[Thingino] ✅ Detection committed to database (ID: {db_detection.id})")
                    
                    # Refresh to ensure we have the latest data
                    db.refresh(db_detection)
                    logger.info(f"[Thingino] ✅ Detection refreshed from database (ID: {db_detection.id})")
                except Exception as commit_error:
                    db.rollback()
                    logger.error(f"[Thingino] ❌ Failed to save detection to database: {commit_error}", exc_info=True)
                    raise  # Re-raise to be handled by outer exception handler
                
                # Log webhook detection
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK",
                    resource_type="detection",
                    resource_id=db_detection.id,
                    details={
                        "camera_id": camera_id,
                        "species": detection_data["species"],
                        "confidence": detection_data["confidence"],
                        "source": "thingino_webhook"
                    }
                )
                
                # Get camera information for broadcasting
                camera_info = db.query(Camera).filter(Camera.id == camera_id).first()
                camera_name = camera_info.name if camera_info else "Thingino Camera"
                
                # Send email notification if enabled and confidence is high enough
                if detection_data.get("confidence", 0) >= 0.7:
                    try:
                        notification_service.send_detection_notification(
                            species=detection_data["species"],
                            confidence=detection_data["confidence"],
                            camera_id=camera_id,
                            camera_name=camera_name,
                            detection_id=db_detection.id,
                            image_url=f"/api/thingino/image/{db_detection.id}",
                            timestamp=db_detection.timestamp
                        )
                    except Exception as e:
                        logging.warning(f"Failed to send notification: {e}")
                
                logger.info(f"[Thingino] Detection saved: ID={db_detection.id}, Species={detection_data['species']}, Confidence={detection_data['confidence']:.2f}")
                
                # Broadcast the new detection to connected clients
                detection_event = {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "species": detection_data["species"],
                    "confidence": detection_data["confidence"],
                    "image_path": temp_path,
                    "timestamp": db_detection.timestamp.isoformat(),
                    "media_url": f"/api/thingino/image/{db_detection.id}"
                }
                # Use asyncio to call the async broadcast
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(event_manager.broadcast_detection(detection_event))
                    else:
                        asyncio.run(event_manager.broadcast_detection(detection_event))
                    logger.info(f"[Thingino] ✅ Detection broadcast to clients (ID: {db_detection.id})")
                except Exception as broadcast_error:
                    logger.warning(f"[Thingino] ⚠️ Failed to broadcast detection (ID: {db_detection.id}): {broadcast_error}")
                    # Don't fail the webhook if broadcast fails - detection is already saved
                
            except Exception as e:
                import traceback
                print(f"ERROR processing detection: {e}")
                # Log failed webhook processing
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK",
                    resource_type="detection",
                    success=False,
                    error_message=str(e),
                    details={"source": "thingino_webhook", "camera_id": camera_id}
                )
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
            
            # Return success response
            return {
                "status": "success",
                "message": "Motion detection processed successfully"
            }
            
        except Exception as e:
            print(f"Error processing Thingino webhook: {str(e)}")
            return {"status": "error", "message": str(e)}

    @router.post("/api/motioneye/webhook")
    async def motioneye_webhook(request: Request, db: Session = Depends(get_db)):
        """Handle MotionEye webhook notifications for motion detection"""
        error_details = {}
        payload = {}
        try:
            payload = await parse_motioneye_payload(request)
            data = payload["raw"]
            camera_id = payload["camera_id"]
            file_path = payload["file_path"]
            timestamp = payload["timestamp"]
            event_type = payload["event_type"]

            # Log webhook receipt for debugging camera detection issues
            logger.info(f"MotionEye webhook received - camera_id: {camera_id}, file_path: {file_path}, event_type: {event_type}, payload keys: {list(data.keys()) if data else 'empty'}")
            
            # Log which cameras are sending webhooks (for debugging detection issues)
            camera = db.query(Camera).filter(Camera.id == camera_id).first()
            camera_name = camera.name if camera else f"Camera {camera_id}"
            logger.info(f"📹 Webhook from {camera_name} (ID: {camera_id}) - Event: {event_type}")
            
            # Additional logging for Camera 8 (WYZECAM3-01) debugging
            if camera_id == 8 or (camera and "WYZECAM3-01" in camera.name.upper()):
                logger.info(f"🔍 Camera 8 Debug - camera_id: {camera_id}, camera_name: {camera_name}, file_path: {file_path}")
                logger.info(f"🔍 Camera 8 Debug - Camera exists in DB: {camera is not None}, Event type: {event_type}")

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("MotionEye webhook payload: %s", data)

            if not camera_id or not file_path:
                error_details = {
                    "missing_camera_id": camera_id is None,
                    "missing_file_path": file_path is None,
                    "payload_keys": list(data.keys()) if data else [],
                    "payload_size": len(str(data)) if data else 0
                }
                
                if not data:
                    logger.warning("⚠️ MotionEye webhook: Empty payload received", extra=error_details)
                    log_audit_event(
                        db=db,
                        request=request,
                        action="WEBHOOK_IGNORED",
                        resource_type="webhook",
                        details={
                            "reason": "empty_payload",
                            **error_details
                        },
                        success=False,
                        error_message="Empty webhook payload"
                    )
                else:
                    logger.warning(
                        f"⚠️ MotionEye webhook: Missing required data (camera_id: {camera_id}, file_path: {bool(file_path)})",
                        extra=error_details
                    )
                    log_audit_event(
                        db=db,
                        request=request,
                        action="WEBHOOK_IGNORED",
                        resource_type="webhook",
                        details={
                            "reason": "missing_required_data",
                            **error_details
                        },
                        success=False,
                        error_message=f"Missing camera_id or file_path. Payload keys: {list(data.keys())}"
                    )
                return {
                    "status": "ignored",
                    "message": "Missing required data",
                    "details": error_details
                }

            if not should_process_event(file_path):
                logger.debug("Ignoring duplicate MotionEye webhook for %s", file_path)
                return {"status": "ignored", "message": "Duplicate event"}
            
            # Convert MotionEye file path to local path
            # MotionEye stores files in /var/lib/motioneye inside the container
            # We need to map this to our local motioneye_media directory
            # Get the absolute path to the wildlife-app directory
            # __file__ is: wildlife-app/backend/routers/webhooks.py
            # We need: wildlife-app/
            current_file = os.path.abspath(__file__)  # .../wildlife-app/backend/routers/webhooks.py
            routers_dir = os.path.dirname(current_file)  # .../wildlife-app/backend/routers
            backend_dir = os.path.dirname(routers_dir)  # .../wildlife-app/backend
            wildlife_app_dir = os.path.dirname(backend_dir)  # .../wildlife-app
            
            # Extract the relative path from MotionEye's path
            # MotionEye sends: /var/lib/motioneye/Camera1/2025-06-26/13-57-02.jpg
            # We want: motioneye_media/Camera1/2025-06-26/13-57-02.jpg
            if file_path.startswith("/var/lib/motioneye/"):
                relative_path = file_path[len("/var/lib/motioneye/"):]
                local_file_path = os.path.join(wildlife_app_dir, "motioneye_media", relative_path)
            else:
                # Fallback: try direct replacement
                local_file_path = file_path.replace("/var/lib/motioneye", os.path.join(wildlife_app_dir, "motioneye_media"))
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("MotionEye path %s mapped to %s", file_path, local_file_path)
            
            # Check if file exists
            if not os.path.exists(local_file_path):
                # Check if parent directory exists
                parent_dir = os.path.dirname(local_file_path)
                parent_exists = os.path.exists(parent_dir)
                
                error_details = {
                    "file_path": local_file_path,
                    "original_path": file_path,
                    "parent_dir": parent_dir,
                    "parent_dir_exists": parent_exists,
                    "wildlife_app_dir": wildlife_app_dir,
                    "motioneye_media_exists": os.path.exists(os.path.join(wildlife_app_dir, "motioneye_media"))
                }
                
                logger.warning(
                    f"⚠️ MotionEye file not found: {local_file_path}",
                    extra=error_details
                )
                
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK_ERROR",
                    resource_type="webhook",
                    resource_id=camera_id,
                    details={
                        "error_category": "file_not_found",
                        "issue": "Image file does not exist at expected path",
                        "suggestion": "Check MotionEye media directory mapping and file synchronization",
                        **error_details
                    },
                    success=False,
                    error_message=f"File not found: {local_file_path}"
                )
                
                return {
                    "status": "error",
                    "message": "File not found",
                    "error_category": "file_not_found",
                    "details": error_details
                }
            
            # Extract date and camera name from the file path for media URL
            path_parts = local_file_path.split(os.sep)
            extracted_camera_name = None
            file_date = None
            
            # Find camera name and date in the path
            for i, part in enumerate(path_parts):
                if part == "motioneye_media" and i + 1 < len(path_parts):
                    extracted_camera_name = path_parts[i + 1]  # Camera1, Camera2, etc.
                if extracted_camera_name and i + 1 < len(path_parts) and "-" in part and len(part) == 10:
                    file_date = part  # 2025-06-26
                    break
            
            # If we couldn't extract date from path, use current date as fallback
            if not file_date:
                file_date = datetime.now().strftime('%Y-%m-%d')
            
            # If we couldn't extract camera name, use camera_id as fallback
            if not extracted_camera_name:
                extracted_camera_name = f"Camera{camera_id}"
            
            # Only process image files (not videos for now)
            if not local_file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                logger.debug("Skipping non-image MotionEye file: %s", local_file_path)
                return {"status": "skipped", "message": "Not an image file"}
            
            # Skip motion mask files (files ending with "m.jpg" or "m.jpeg")
            # These are debug images showing motion detection areas, not actual wildlife photos
            filename = os.path.basename(local_file_path).lower()
            if filename.endswith('m.jpg') or filename.endswith('m.jpeg'):
                logger.debug("Skipping motion mask image: %s", local_file_path)
                return {"status": "skipped", "message": "Motion mask file (not processed)"}
            
            # Process image with SpeciesNet
            try:
                predictions = speciesnet_processor.process_image(local_file_path)
                if not predictions or "error" in predictions:
                    error_msg = predictions.get("error", "Unknown SpeciesNet error") if isinstance(predictions, dict) else "No predictions returned"
                    logger.warning(
                        f"⚠️ SpeciesNet processing failed for {local_file_path}: {error_msg}",
                        extra={
                            "camera_id": camera_id,
                            "file_path": local_file_path,
                            "error": error_msg
                        }
                    )
                    log_audit_event(
                        db=db,
                        request=request,
                        action="WEBHOOK_ERROR",
                        resource_type="webhook",
                        resource_id=camera_id,
                        details={
                            "error_category": "speciesnet_error",
                            "issue": "SpeciesNet image processing failed",
                            "error": error_msg,
                            "suggestion": "Check SpeciesNet server status and image file validity"
                        },
                        success=False,
                        error_message=f"SpeciesNet error: {error_msg}"
                    )
                    return {
                        "status": "error",
                        "message": "SpeciesNet processing failed",
                        "error_category": "speciesnet_error",
                        "details": {"error": error_msg}
                    }
            except Exception as speciesnet_error:
                error_type = type(speciesnet_error).__name__
                logger.error(
                    f"❌ SpeciesNet processing exception: {error_type}: {str(speciesnet_error)}",
                    extra={
                        "camera_id": camera_id,
                        "file_path": local_file_path,
                        "error_type": error_type,
                        "error_message": str(speciesnet_error)
                    },
                    exc_info=True
                )
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK_ERROR",
                    resource_type="webhook",
                    resource_id=camera_id,
                    details={
                        "error_category": "speciesnet_exception",
                        "error_type": error_type,
                        "error_message": str(speciesnet_error),
                        "suggestion": "Check SpeciesNet server connectivity and image file format"
                    },
                    success=False,
                    error_message=f"{error_type}: {str(speciesnet_error)}"
                )
                raise  # Re-raise to be caught by outer exception handler
            
            # Use smart detection processor for enhanced analysis
            from services.smart_detection import SmartDetectionProcessor
            smart_processor = SmartDetectionProcessor(db=db)
            detection_timestamp = datetime.now()
            
            # Analyze predictions with smart detection
            analysis = smart_processor.process_detection(
                predictions=predictions,
                camera_id=camera_id,
                timestamp=detection_timestamp
            )
            
            # Extract basic detection info for fallback
            basic_species = "Unknown"
            basic_confidence = 0.0
            if predictions.get("predictions") and len(predictions["predictions"]) > 0:
                top_pred = predictions["predictions"][0]
                basic_species = top_pred.get("prediction", "Unknown")
                basic_confidence = float(top_pred.get("prediction_score", 0.0))
            
            # Check if detection should be saved
            should_save = smart_processor.should_save_detection(analysis)
            
            # Log detection analysis for debugging
            logger.info(f"🔍 Detection analysis - Species: {analysis.get('species', 'Unknown')}, Confidence: {analysis.get('confidence', 0.0):.3f}, Should save: {should_save}, Quality: {analysis.get('quality', 'unknown')}")
            
            # Fallback: If smart detection says don't save, but we have a reasonable prediction, save it anyway
            # This ensures we don't lose detections due to overly strict filtering
            if not should_save and basic_confidence >= 0.15:
                logger.info(f"⚠️ Smart detection filtered detection, but using fallback (confidence: {basic_confidence:.3f}, species: {basic_species})")
                should_save = True
                # Use basic detection data instead of smart detection
                analysis = {
                    "species": basic_species,
                    "confidence": basic_confidence,
                    "quality": "fallback",
                    "should_save": True,
                    "should_notify": basic_confidence >= 0.7,
                    "all_predictions": predictions.get("predictions", [])[:5] if predictions.get("predictions") else []
                }
            
            if "error" in analysis:
                logger.warning("Smart detection analysis error: %s", analysis.get("error", "Unknown error"))
                # Still save the detection even on error, but with error info
                detection_data = smart_processor.get_detection_data(
                    analysis=analysis,
                    image_path=local_file_path,
                    camera_id=camera_id,
                    timestamp=detection_timestamp
                )
            elif not should_save:
                confidence = analysis.get("confidence", 0.0)
                species = analysis.get("species", "Unknown")
                logger.info("⚠️ Skipping detection save: confidence too low (confidence: %.3f, species: %s, min_required: %.2f)", 
                           confidence,
                           species,
                           smart_processor.min_confidence_to_save)
                # Log to audit for tracking filtered detections
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK_FILTERED",
                    resource_type="detection",
                    resource_id=camera_id,
                    details={
                        "reason": "low_confidence",
                        "confidence": confidence,
                        "species": species,
                        "min_confidence_required": smart_processor.min_confidence_to_save,
                        "file_path": local_file_path
                    },
                    success=False,
                    error_message=f"Detection filtered: confidence {confidence:.3f} below threshold {smart_processor.min_confidence_to_save}"
                )
                # Don't save this detection - return early
                return {
                    "status": "skipped",
                    "message": "Detection not saved (low confidence or quality check failed)",
                    "reason": "should_not_save",
                    "confidence": confidence,
                    "species": species,
                    "min_confidence_required": smart_processor.min_confidence_to_save
                }
            else:
                # Use smart detection results
                detection_data = smart_processor.get_detection_data(
                    analysis=analysis,
                    image_path=local_file_path,
                    camera_id=camera_id,
                    timestamp=detection_timestamp
                )
                
                logger.info("Smart detection: %s (confidence: %.2f, quality: %s, gap: %.2f)",
                           analysis["species"],
                           analysis["confidence"],
                           analysis["quality"],
                           analysis.get("confidence_gap", 0.0))
            
            # Create detection record
            try:
                db_detection = Detection(**detection_data)
                db.add(db_detection)
                db.flush()  # Flush to get the ID without committing yet
                logger.info(f"✅ Detection created in database (ID: {db_detection.id}, Camera: {camera_id}, Species: {detection_data['species']}, Confidence: {detection_data['confidence']:.2f})")
                
                # Commit the detection
                db.commit()
                logger.info(f"✅ Detection committed to database (ID: {db_detection.id})")
                
                # Refresh to ensure we have the latest data
                db.refresh(db_detection)
                logger.info(f"✅ Detection refreshed from database (ID: {db_detection.id})")
            except Exception as commit_error:
                db.rollback()
                logger.error(f"❌ Failed to save detection to database: {commit_error}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save detection to database: {str(commit_error)}"
                )
            
            # Send notification if high confidence (using smart detection analysis)
            if not "error" in analysis and analysis.get("should_notify", False):
                try:
                    notification_service.send_detection_notification(
                        species=analysis["species"],
                        confidence=analysis["confidence"],
                        camera_id=camera_id,
                        detection_id=db_detection.id,
                        timestamp=db_detection.timestamp
                    )
                except Exception as e:
                    logger.warning(f"Failed to send notification: {e}")
            
            # Trigger webhooks for detection (using smart detection analysis)
            try:
                webhook_service = WebhookService(db)
                detection_data_webhook = {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "species": analysis.get("species", "Unknown"),
                    "confidence": analysis.get("confidence", 0.0),
                    "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                    "image_path": db_detection.image_path,
                    "quality": analysis.get("quality", "unknown")
                }
                webhook_service.trigger_detection_webhooks(
                    detection_data=detection_data_webhook,
                    confidence=analysis.get("confidence", 0.0),
                    species=analysis.get("species", "Unknown")
                )
            except Exception as e:
                logger.warning(f"Failed to trigger webhooks: {e}")
            
            # Log MotionEye webhook detection
            log_audit_event(
                db=db,
                request=request,
                action="WEBHOOK",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": analysis.get("species", "Unknown"),
                    "confidence": analysis.get("confidence", 0.0),
                    "quality": analysis.get("quality", "unknown"),
                    "source": "motioneye_webhook",
                    "file_path": local_file_path
                }
            )
            
            # Get camera information for the response - use database name if available, otherwise use extracted name
            camera_info = db.query(Camera).filter(Camera.id == camera_id).first()
            camera_name = camera_info.name if camera_info else extracted_camera_name
            
            # Broadcast the new detection to connected clients
            detection_event = {
                "id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "species": detection_data["species"],
                "confidence": detection_data["confidence"],
                "image_path": local_file_path,
                "timestamp": db_detection.timestamp.isoformat(),
                "media_url": f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}"
            }
            
            try:
                await event_manager.broadcast_detection(detection_event)
                logger.info(f"✅ Detection broadcast to clients (ID: {db_detection.id})")
            except Exception as broadcast_error:
                logger.warning(f"⚠️ Failed to broadcast detection (ID: {db_detection.id}): {broadcast_error}")
                # Don't fail the webhook if broadcast fails - detection is already saved
            
            return {
                "status": "success",
                "detection_id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "species": detection_data["species"],
                "confidence": detection_data["confidence"],
                "file_path": local_file_path,
                "media_url": f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}"
            }
            
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            # Categorize error types for better diagnostics
            error_category = "unknown"
            error_details = {}
            
            if "file_path" in error_message.lower() or "file" in error_message.lower():
                error_category = "file_path_error"
                error_details = {
                    "issue": "File path processing error",
                    "suggestion": "Check MotionEye webhook payload format and file path extraction logic"
                }
            elif "database" in error_message.lower() or "sql" in error_message.lower() or "session" in error_message.lower():
                error_category = "database_error"
                error_details = {
                    "issue": "Database operation failed",
                    "suggestion": "Check database connection and table schema"
                }
            elif "speciesnet" in error_message.lower() or "prediction" in error_message.lower():
                error_category = "speciesnet_error"
                error_details = {
                    "issue": "SpeciesNet processing failed",
                    "suggestion": "Check SpeciesNet server status and image processing pipeline"
                }
            elif "permission" in error_message.lower() or "access" in error_message.lower():
                error_category = "permission_error"
                error_details = {
                    "issue": "File access permission denied",
                    "suggestion": "Check file permissions and path accessibility"
                }
            elif "not found" in error_message.lower():
                error_category = "not_found_error"
                error_details = {
                    "issue": "Resource not found",
                    "suggestion": "Verify camera exists and file path is correct"
                }
            
            # Log detailed error information
            logger.error(
                f"❌ MotionEye Webhook Error [{error_category}] - {error_type}: {error_message}",
                extra={
                    "error_type": error_type,
                    "error_category": error_category,
                    "error_message": error_message,
                    "camera_id": payload.get("camera_id") if 'payload' in locals() else None,
                    "file_path": payload.get("file_path") if 'payload' in locals() else None,
                    "event_type": payload.get("event_type") if 'payload' in locals() else None,
                    "traceback": error_traceback
                },
                exc_info=True
            )
            
            # Log to audit log for tracking
            try:
                log_audit_event(
                    db=db,
                    request=request,
                    action="WEBHOOK_ERROR",
                    resource_type="webhook",
                    details={
                        "error_type": error_type,
                        "error_category": error_category,
                        "error_message": error_message,
                        "camera_id": payload.get("camera_id") if 'payload' in locals() else None,
                        "file_path": payload.get("file_path") if 'payload' in locals() else None,
                        "event_type": payload.get("event_type") if 'payload' in locals() else None,
                        "suggestion": error_details.get("suggestion", "Check logs for details")
                    },
                    success=False,
                    error_message=f"{error_type}: {error_message}"
                )
            except Exception as audit_error:
                logger.warning(f"Failed to log webhook error to audit log: {audit_error}")
            
            # Return detailed error response
            error_response = {
                "status": "error",
                "error_type": error_type,
                "error_category": error_category,
                "message": error_message,
                "details": error_details,
                "timestamp": datetime.now().isoformat()
            }
            
            # Include traceback in debug mode
            if logger.isEnabledFor(logging.DEBUG):
                error_response["traceback"] = error_traceback
            
            raise HTTPException(status_code=500, detail=error_response)

    @router.post("/api/webhooks", response_model=WebhookResponse)
    @limiter.limit("10/hour")
    def create_webhook(
        request: Request,
        webhook: WebhookCreate,
        db: Session = Depends(get_db)
    ):
        """Create a new webhook"""
        try:
            db_webhook = Webhook(**webhook.model_dump())
            db.add(db_webhook)
            db.commit()
            db.refresh(db_webhook)
            
            log_audit_event(
                db=db,
                request=request,
                action="CREATE",
                resource_type="webhook",
                resource_id=db_webhook.id,
                details={"name": webhook.name, "url": webhook.url, "event_type": webhook.event_type}
            )
            
            return db_webhook
        except Exception as e:
            db.rollback()
            logging.error(f"Failed to create webhook: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")

    @router.get("/api/webhooks", response_model=List[WebhookResponse])
    @limiter.limit("60/minute")
    def list_webhooks(
        request: Request,
        is_active: Optional[bool] = None,
        event_type: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """List all webhooks"""
        try:
            query = db.query(Webhook)
            
            if is_active is not None:
                query = query.filter(Webhook.is_active == is_active)
            
            if event_type:
                query = query.filter(Webhook.event_type == event_type)
            
            webhooks = query.order_by(Webhook.created_at.desc()).all()
            return webhooks
        except Exception as e:
            logging.error(f"Failed to list webhooks: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")

    @router.get("/api/webhooks/{webhook_id}", response_model=WebhookResponse)
    @limiter.limit("60/minute")
    def get_webhook(
        request: Request,
        webhook_id: int,
        db: Session = Depends(get_db)
    ):
        """Get a specific webhook"""
        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return webhook

    @router.put("/api/webhooks/{webhook_id}", response_model=WebhookResponse)
    @limiter.limit("10/hour")
    def update_webhook(
        request: Request,
        webhook_id: int,
        webhook: WebhookCreate,
        db: Session = Depends(get_db)
    ):
        """Update a webhook"""
        try:
            db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
            if not db_webhook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            
            for key, value in webhook.model_dump().items():
                setattr(db_webhook, key, value)
            
            db.commit()
            db.refresh(db_webhook)
            
            log_audit_event(
                db=db,
                request=request,
                action="UPDATE",
                resource_type="webhook",
                resource_id=webhook_id,
                details={"name": webhook.name}
            )
            
            return db_webhook
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logging.error(f"Failed to update webhook: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to update webhook: {str(e)}")

    @router.delete("/api/webhooks/{webhook_id}")
    @limiter.limit("10/hour")
    def delete_webhook(
        request: Request,
        webhook_id: int,
        db: Session = Depends(get_db)
    ):
        """Delete a webhook"""
        try:
            db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
            if not db_webhook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            
            webhook_name = db_webhook.name
            db.delete(db_webhook)
            db.commit()
            
            log_audit_event(
                db=db,
                request=request,
                action="DELETE",
                resource_type="webhook",
                resource_id=webhook_id,
                details={"name": webhook_name}
            )
            
            return {"success": True, "message": "Webhook deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logging.error(f"Failed to delete webhook: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to delete webhook: {str(e)}")

    @router.post("/api/webhooks/{webhook_id}/test")
    @limiter.limit("10/hour")
    def test_webhook(
        request: Request,
        webhook_id: int,
        db: Session = Depends(get_db)
    ):
        """Test a webhook by sending a test payload"""
        try:
            webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
            if not webhook:
                raise HTTPException(status_code=404, detail="Webhook not found")
            
            webhook_service = WebhookService(db)
            
            # Send test payload
            test_payload = {
                "event": "test",
                "message": "This is a test webhook from Wildlife App",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            success = webhook_service.trigger_webhook(webhook, test_payload, "test")
            
            return {
                "success": success,
                "message": "Test webhook sent successfully" if success else "Test webhook failed"
            }
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Failed to test webhook: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to test webhook: {str(e)}")

    return router
