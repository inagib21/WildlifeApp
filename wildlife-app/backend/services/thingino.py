"""Thingino camera service"""
import os
import json
import tempfile
import logging
import requests
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from fastapi import Request

try:
    from ..database import Detection, Camera
    from ..services.ai_backends import ai_backend_manager
    from ..services.notifications import notification_service
    from ..services.events import get_event_manager
    from ..utils.audit import log_audit_event
    from ..config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD
except ImportError:
    # Handle direct import for testing/scripts
    from database import Detection, Camera
    from services.ai_backends import ai_backend_manager
    from services.notifications import notification_service
    from services.events import get_event_manager
    from utils.audit import log_audit_event
    from config import THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD

logger = logging.getLogger(__name__)


class ThinginoService:
    """Service for handling Thingino camera interactions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_manager = get_event_manager()
    
    async def process_webhook(self, request: Request, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process webhook from Thingino camera"""
        message = data.get("message", "Motion detected")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        image_url = data.get("image_url", "http://192.168.88.93/x/preview.cgi")
        
        # Determine camera ID based on the image URL
        if "192.168.88.97" in image_url:
            camera_id = 10  # Thingino Camera 2
        else:
            camera_id = 9   # Thingino Camera 1 (default)
        
        logger.info(f"Processing Thingino motion detection for camera {camera_id}: {message}")
        
        try:
            # Use authentication for Thingino cameras
            auth = None
            if "192.168.88.93" in image_url or "192.168.88.97" in image_url:
                auth = (THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD)
            
            # Download image
            try:
                response = requests.get(image_url, auth=auth, timeout=15)
                if response.status_code != 200:
                    logger.error(f"Failed to download image from Thingino: HTTP {response.status_code}")
                    return {"status": "error", "message": f"Failed to download image: HTTP {response.status_code}"}
            except Exception as e:
                logger.error(f"Failed to connect to Thingino: {e}")
                return {"status": "error", "message": f"Connection failed: {str(e)}"}
            
            # Save image temporarily
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thingino_motion_{timestamp_str}.jpg"
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            logger.debug(f"Image saved to: {temp_path}")
            
            # Process with AI Backend Manager
            predictions = ai_backend_manager.predict(temp_path)
            
            detection_data = self._prepare_detection_data(
                camera_id=camera_id,
                temp_path=temp_path,
                predictions=predictions
            )
            
            # Save detection
            saved_detection = self._save_detection(detection_data)
            
            # Log audit event
            log_audit_event(
                db=self.db,
                request=request,
                action="WEBHOOK",
                resource_type="detection",
                resource_id=saved_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": detection_data["species"],
                    "confidence": detection_data["confidence"],
                    "source": "thingino_webhook"
                }
            )
            
            # Notifications and Broadcasting
            await self._handle_notifications_and_broadcast(
                detection=saved_detection,
                detection_data=detection_data,
                camera_id=camera_id,
                temp_path=temp_path
            )
            
            logger.info(f"[Thingino] Detection processed: ID={saved_detection.id}, Species={detection_data['species']}")
            
            return {
                "status": "success",
                "message": "Motion detection processed successfully",
                "detection_id": saved_detection.id
            }
            
        except Exception as e:
            logger.error(f"Error processing Thingino webhook: {str(e)}", exc_info=True)
            # Log failed webhook
            log_audit_event(
                db=self.db,
                request=request,
                action="WEBHOOK_ERROR",
                resource_type="webhook",
                success=False,
                error_message=str(e),
                details={"source": "thingino_webhook", "camera_id": camera_id}
            )
            return {"status": "error", "message": str(e)}

    def _prepare_detection_data(self, camera_id: int, temp_path: str, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for detection record"""
        species = "Unknown"
        confidence = 0.0
        
        if "error" in predictions:
            logger.warning(f"AI processing error: {predictions['error']}")
            detections_json = json.dumps({"error": predictions["error"]})
        else:
            detections_json = json.dumps(predictions)
            if "predictions" in predictions and predictions["predictions"]:
                pred = predictions["predictions"][0]
                species = pred.get("prediction", "Unknown")
                confidence = pred.get("prediction_score", 0.0)
        
        return {
            "camera_id": camera_id,
            "timestamp": datetime.now(),
            "species": species,
            "confidence": confidence,
            "image_path": temp_path,
            "detections_json": detections_json,
            "prediction_score": confidence
        }

    def _save_detection(self, data: Dict[str, Any]) -> Detection:
        """Save detection to database"""
        try:
            db_detection = Detection(**data)
            self.db.add(db_detection)
            self.db.commit()
            self.db.refresh(db_detection)
            return db_detection
        except Exception as e:
            self.db.rollback()
            raise e

    async def _handle_notifications_and_broadcast(self, detection: Detection, detection_data: Dict[str, Any], camera_id: int, temp_path: str):
        """Handle notifications and websocket broadcasting"""
        # Get camera info
        camera = self.db.query(Camera).filter(Camera.id == camera_id).first()
        camera_name = camera.name if camera else "Thingino Camera"
        
        # Email Notification
        if detection_data.get("confidence", 0) >= 0.7:
            try:
                notification_service.send_detection_notification(
                    species=detection_data["species"],
                    confidence=detection_data["confidence"],
                    camera_id=camera_id,
                    camera_name=camera_name,
                    detection_id=detection.id,
                    image_url=f"/api/thingino/image/{detection.id}",
                    timestamp=detection.timestamp
                )
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
        
        # Websocket Broadcast
        detection_event = {
            "id": detection.id,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "species": detection_data["species"],
            "confidence": detection_data["confidence"],
            "image_path": temp_path,
            "timestamp": detection.timestamp.isoformat(),
            "media_url": f"/api/thingino/image/{detection.id}"
        }
        
        try:
            # We can run this directly if we are in an async context (which we are)
            await self.event_manager.broadcast_detection(detection_event)
        except Exception as e:
            logger.warning(f"Failed to broadcast detection: {e}")
