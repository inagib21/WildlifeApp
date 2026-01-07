"""MotionEye Webhook Handler Service"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from fastapi import Request, HTTPException

try:
    from ..database import Detection, Camera
    from ..services.ai_backends import ai_backend_manager
    from ..services.smart_detection import SmartDetectionProcessor
    from ..services.notifications import notification_service
    from ..services.events import get_event_manager
    from ..services.webhooks import WebhookService
    from ..utils.audit import log_audit_event
    from ..motioneye_webhook import parse_motioneye_payload
    from ..motioneye_events import should_process_event
except ImportError:
    from database import Detection, Camera
    from services.ai_backends import ai_backend_manager
    from services.smart_detection import SmartDetectionProcessor
    from services.notifications import notification_service
    from services.events import get_event_manager
    from services.webhooks import WebhookService
    from utils.audit import log_audit_event
    from motioneye_webhook import parse_motioneye_payload
    from motioneye_events import should_process_event

logger = logging.getLogger(__name__)


class MotionEyeWebhookHandler:
    """Handler for MotionEye webhook events"""
    
    def __init__(self, db: Session):
        self.db = db
        self.event_manager = get_event_manager()
        self.smart_processor = SmartDetectionProcessor(db=db)
    
    async def process_webhook(self, request: Request, wildlife_app_dir: str) -> Dict[str, Any]:
        """Process MotionEye webhook"""
        payload = {}
        error_details = {}
        
        try:
            # Parse payload
            payload = await parse_motioneye_payload(request)
            data = payload["raw"]
            camera_id = payload["camera_id"]
            file_path = payload["file_path"]
            timestamp = payload["timestamp"]
            
            # Basic validation
            if not camera_id or not file_path:
                return self._handle_missing_data(request, data, camera_id, file_path)
            
            # Check for duplicate events
            if not should_process_event(file_path):
                return {"status": "ignored", "message": "Duplicate event"}
            
            # Resolve local file path
            local_file_path = self._resolve_file_path(file_path, wildlife_app_dir)
            
            # Validate file existence
            if not os.path.exists(local_file_path):
                return self._handle_file_not_found(request, local_file_path, file_path, camera_id)
            
            # Filter non-image files
            if self._should_skip_file(local_file_path):
                 return {"status": "skipped", "message": "File skipped (not image or motion mask)"}

            # Process AI Detection
            predictions = await self._run_ai_processing(local_file_path, camera_id, request)
            
            # Determine camera name and file date for URLs
            camera_info = self.db.query(Camera).filter(Camera.id == camera_id).first()
            extracted_camera_name = self._extract_camera_name(local_file_path, camera_id)
            camera_name = camera_info.name if camera_info else extracted_camera_name
            file_date = self._extract_file_date(local_file_path)
            
            # Smart Analysis
            analysis = self.smart_processor.process_detection(
                predictions=predictions,
                camera_id=camera_id,
                timestamp=datetime.now(),
                image_path=local_file_path
            )
            
            # Save Decision
            should_save = self.smart_processor.should_save_detection(analysis)
            
            # Fallback logic for basic confidence
            basic_confidence = self._get_basic_confidence(predictions)
            if not should_save and basic_confidence >= 0.15:
                should_save = True
                analysis["should_save"] = True
                analysis["quality"] = "fallback"
            
            if not should_save:
                return self._handle_filtered_detection(request, camera_id, local_file_path, analysis)
            
            # Save detection
            detection_data = self.smart_processor.get_detection_data(
                analysis=analysis,
                image_path=local_file_path,
                camera_id=camera_id,
                timestamp=datetime.now()
            )
            
            db_detection = self._save_detection_to_db(detection_data)
            
            # Post-save actions (Notify, Webhooks, Broadcast)
            await self._handle_post_save_actions(
                db_detection, 
                camera_id, 
                camera_name, 
                analysis, 
                extracted_camera_name,
                file_date,
                local_file_path
            )
            
            # Log success
            log_audit_event(
                db=self.db,
                request=request,
                action="WEBHOOK",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": analysis.get("species", "Unknown"),
                    "confidence": analysis.get("confidence", 0.0),
                    "source": "motioneye_webhook"
                }
            )
            
            return {
                "status": "success",
                "detection_id": db_detection.id,
                "camera_name": camera_name,
                "species": detection_data["species"],
                "confidence": detection_data["confidence"]
            }
            
        except Exception as e:
            logger.error(f"Error processing MotionEye webhook: {e}", exc_info=True)
            log_audit_event(
                db=self.db,
                request=request,
                action="WEBHOOK_ERROR",
                resource_type="webhook",
                success=False,
                error_message=str(e),
                details={"camera_id": payload.get("camera_id") if payload else 'unknown'}
            )
            return {"status": "error", "message": str(e)}

    def _resolve_file_path(self, file_path: str, wildlife_app_dir: str) -> str:
        """Map MotionEye internal path to local path"""
        if file_path.startswith("/var/lib/motioneye/"):
            relative_path = file_path[len("/var/lib/motioneye/"):]
            return os.path.join(wildlife_app_dir, "motioneye_media", relative_path)
        return file_path.replace("/var/lib/motioneye", os.path.join(wildlife_app_dir, "motioneye_media"))

    def _handle_missing_data(self, request, data, camera_id, file_path):
        log_audit_event(
            db=self.db,
            request=request,
            action="WEBHOOK_IGNORED",
            resource_type="webhook",
            details={"reason": "missing_data"},
            success=False,
            error_message="Missing required data"
        )
        return {"status": "ignored", "message": "Missing required data"}

    def _handle_file_not_found(self, request, local_path, original_path, camera_id):
        log_audit_event(
            db=self.db,
            request=request,
            action="WEBHOOK_ERROR",
            resource_type="webhook",
            resource_id=camera_id,
            details={"path": local_path},
            success=False,
            error_message=f"File not found: {local_path}"
        )
        return {"status": "error", "message": "File not found"}

    def _should_skip_file(self, file_path: str) -> bool:
        if not file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            return True
        filename = os.path.basename(file_path).lower()
        if filename.endswith('m.jpg') or filename.endswith('m.jpeg'):
            return True
        return False

    async def _run_ai_processing(self, file_path: str, camera_id: int, request: Request) -> Dict[str, Any]:
        """Run AI prediction with error handling"""
        try:
            # Use configured backend or default
            try:
                from ..config import AI_BACKEND
            except ImportError:
                from config import AI_BACKEND
            
            predictions = ai_backend_manager.predict(file_path, backend_name=AI_BACKEND)
            if "error" in predictions:
                logger.warning(f"AI Error: {predictions['error']}")
                # Log but continue (will result in Unknown/Fallback)
            return predictions
        except Exception as e:
            logger.error(f"AI Exception: {e}")
            return {"error": str(e), "predictions": []}

    def _get_basic_confidence(self, predictions: Dict[str, Any]) -> float:
        if predictions.get("predictions"):
            return float(predictions["predictions"][0].get("prediction_score", 0.0))
        return 0.0

    def _handle_filtered_detection(self, request, camera_id, file_path, analysis):
        log_audit_event(
            db=self.db,
            request=request,
            action="WEBHOOK_FILTERED",
            resource_type="detection",
            resource_id=camera_id,
            details={
                "reason": "low_confidence",
                "species": analysis.get("species"),
                "confidence": analysis.get("confidence")
            },
            success=False,
            error_message="Detection filtered"
        )
        return {"status": "skipped", "message": "Detection filtered (low confidence)"}

    def _save_detection_to_db(self, data: Dict[str, Any]) -> Detection:
        try:
            db_detection = Detection(**data)
            self.db.add(db_detection)
            self.db.commit()
            self.db.refresh(db_detection)
            return db_detection
        except Exception as e:
            self.db.rollback()
            raise e

    async def _handle_post_save_actions(self, db_detection, camera_id, camera_name, analysis, extracted_key, file_date, file_path):
        # Notifications
        if analysis.get("should_notify", False):
            try:
                notification_service.send_detection_notification(
                    species=analysis["species"],
                    confidence=analysis["confidence"],
                    camera_id=camera_id,
                    detection_id=db_detection.id,
                    timestamp=db_detection.timestamp
                )
            except Exception as e:
                logger.warning(f"Notification error: {e}")
        
        # External Webhooks
        try:
            webhook_service = WebhookService(self.db)
            webhook_service.trigger_detection_webhooks(
                detection_data={"id": db_detection.id, "species": analysis.get("species")},
                confidence=analysis.get("confidence", 0),
                species=analysis.get("species", "Unknown")
            )
        except Exception as e:
            logger.warning(f"External webhook error: {e}")
            
        # Broadcast
        try:
            media_url = f"/media/{extracted_key}/{file_date}/{os.path.basename(file_path)}"
            await self.event_manager.broadcast_detection({
                "id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "species": analysis["species"],
                "confidence": analysis["confidence"],
                "media_url": media_url
            })
        except Exception as e:
            logger.warning(f"Broadcast error: {e}")

    def _extract_camera_name(self, file_path: str, camera_id: int) -> str:
        parts = file_path.split(os.sep)
        for i, part in enumerate(parts):
            if part == "motioneye_media" and i + 1 < len(parts):
                return parts[i + 1]
        return f"Camera{camera_id}"

    def _extract_file_date(self, file_path: str) -> str:
        parts = file_path.split(os.sep)
        for part in parts:
             if "-" in part and len(part) == 10: # Simple date check
                 return part
        return datetime.now().strftime('%Y-%m-%d')
