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
except (ImportError, ValueError):
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
                logger.debug(f"Duplicate event ignored: {file_path}")
                return {"status": "ignored", "message": "Duplicate event"}
            
            # Resolve local file path
            local_file_path = self._resolve_file_path(file_path, wildlife_app_dir)
            
            # Validate file existence
            if not os.path.exists(local_file_path):
                return self._handle_file_not_found(request, local_file_path, file_path, camera_id)
            
            # Check if this is a video file - handle video linking
            if self._is_video_file(local_file_path):
                return await self._handle_video_webhook(request, local_file_path, camera_id, timestamp, payload)
            
            # Check if this is an audio file - handle sound detection
            if self._is_audio_file(local_file_path):
                return await self._handle_audio_webhook(request, local_file_path, camera_id, timestamp, payload)
            
            # Filter non-image files
            if self._should_skip_file(local_file_path):
                 return {"status": "skipped", "message": "File skipped (not image or motion mask)"}

            # Process AI Detection
            predictions = await self._run_ai_processing(local_file_path, camera_id, request)
            
            # Process Face Recognition (if enabled and available)
            face_detections = []
            try:
                try:
                    from ..services.face_recognition import face_recognition_service
                except (ImportError, ValueError):
                    from services.face_recognition import face_recognition_service
                if face_recognition_service.is_available():
                    # Load known faces if not already loaded
                    if not face_recognition_service.known_faces:
                        face_recognition_service.load_known_faces(self.db)
                    
                    # Recognize faces in the image
                    face_detections = face_recognition_service.recognize_faces(local_file_path)
                    if face_detections:
                        logger.info(f"Detected {len(face_detections)} face(s) in {local_file_path}")
            except Exception as e:
                logger.warning(f"Face recognition error: {e}")
                # Rollback in case of DB error to prevent transaction abortion
                self.db.rollback()
            
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
                logger.debug(f"Detection filtered out: species={analysis.get('species')}, confidence={analysis.get('confidence')}, camera_id={camera_id}")
                return self._handle_filtered_detection(request, camera_id, local_file_path, analysis)
            
            # Save detection
            detection_data = self.smart_processor.get_detection_data(
                analysis=analysis,
                image_path=local_file_path,
                camera_id=camera_id,
                timestamp=datetime.now()
            )
            
            db_detection = self._save_detection_to_db(detection_data)
            
            # Save face detections to database
            if face_detections:
                try:
                    try:
                        from ..database import FaceDetection
                    except (ImportError, ValueError):
                        from database import FaceDetection
                    import json
                    for face in face_detections:
                        face_detection = FaceDetection(
                            detection_id=db_detection.id,
                            known_face_id=face.get("known_face_id"),
                            confidence=face.get("recognition_confidence", 0.0),
                            face_location=json.dumps(face.get("face_location", {})),
                            face_encoding=json.dumps(face.get("face_encoding", []))
                        )
                        self.db.add(face_detection)
                    self.db.commit()
                    logger.info(f"Saved {len(face_detections)} face detection(s) for detection {db_detection.id}")
                except Exception as e:
                    logger.error(f"Error saving face detections: {e}")
                    self.db.rollback()
            
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
            # Rollback any failed transaction so we can log the error
            self.db.rollback()
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

    def _is_video_file(self, file_path: str) -> bool:
        """Check if file is a video file"""
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ogv')
        return file_path.lower().endswith(video_extensions)
    
    def _is_audio_file(self, file_path: str) -> bool:
        """Check if file is an audio file"""
        audio_extensions = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma')
        return file_path.lower().endswith(audio_extensions)
    
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
            # Check if AI processing is enabled
            try:
                from ..routers.settings import get_setting
            except (ImportError, ValueError):
                from routers.settings import get_setting
            
            ai_enabled = get_setting(self.db, "ai_enabled", default=True)
            if not ai_enabled:
                logger.info("AI processing is disabled, skipping AI analysis")
                return {
                    "predictions": [{"prediction": "Unknown", "prediction_score": 0.0}],
                    "model": "disabled",
                    "confidence": 0.0
                }
            
            # Use configured backend or default - pass db_session to check enabled status
            try:
                from ..config import AI_BACKEND
            except (ImportError, ValueError):
                from config import AI_BACKEND
            
            predictions = ai_backend_manager.predict(file_path, backend_name=AI_BACKEND, db_session=self.db)
            if "error" in predictions:
                logger.warning(f"AI Error: {predictions['error']}")
                # Log but continue (will result in Unknown/Fallback)
            return predictions
        except Exception as e:
            logger.error(f"AI Exception: {e}")
            # Rollback in case of DB error to prevent transaction abortion
            self.db.rollback()
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
    
    async def _handle_video_webhook(self, request: Request, video_path: str, camera_id: int, timestamp: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle video file webhook - link video to most recent detection"""
        from datetime import timedelta
        
        try:
            # Parse timestamp if provided
            detection_timestamp = None
            if timestamp:
                try:
                    # Try parsing various timestamp formats
                    if isinstance(timestamp, str):
                        # Try ISO format first
                        try:
                            detection_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            # Try parsing as Unix timestamp
                            try:
                                detection_timestamp = datetime.fromtimestamp(float(timestamp))
                            except:
                                pass
                    elif isinstance(timestamp, (int, float)):
                        detection_timestamp = datetime.fromtimestamp(float(timestamp))
                except Exception as e:
                    logger.debug(f"Could not parse timestamp {timestamp}: {e}")
            
            # If no timestamp, use current time (video might be for recent detection)
            if not detection_timestamp:
                detection_timestamp = datetime.now()
            
            # Find the most recent detection for this camera within a reasonable time window
            # Videos are typically created right after the image detection, so look within last 5 minutes
            time_window_start = detection_timestamp - timedelta(minutes=5)
            
            # Query for recent detections for this camera
            recent_detection = self.db.query(Detection).filter(
                Detection.camera_id == camera_id,
                Detection.timestamp >= time_window_start,
                Detection.timestamp <= detection_timestamp + timedelta(minutes=1),  # Allow 1 min after
                Detection.video_path.is_(None)  # Only update detections without videos
            ).order_by(Detection.timestamp.desc()).first()
            
            if recent_detection:
                # Update the detection with video path
                recent_detection.video_path = video_path
                self.db.commit()
                self.db.refresh(recent_detection)
                
                logger.info(f"Linked video {video_path} to detection {recent_detection.id} (camera {camera_id})")
                
                # Log audit event
                log_audit_event(
                    db=self.db,
                    request=request,
                    action="VIDEO_LINKED",
                    resource_type="detection",
                    resource_id=recent_detection.id,
                    details={
                        "camera_id": camera_id,
                        "video_path": video_path,
                        "detection_timestamp": str(recent_detection.timestamp)
                    }
                )
                
                return {
                    "status": "success",
                    "message": "Video linked to detection",
                    "detection_id": recent_detection.id,
                    "video_path": video_path
                }
            else:
                # No matching detection found - video will remain unlinked
                logger.info(f"Video {video_path} received but no matching detection found (camera {camera_id}, timestamp {detection_timestamp})")
                return {
                    "status": "ignored",
                    "message": "No matching detection found for video"
                }
                
        except Exception as e:
            logger.error(f"Error handling video webhook: {e}", exc_info=True)
            self.db.rollback()
            return {
                "status": "error",
                "message": f"Error linking video: {str(e)}"
            }
    
    async def _handle_audio_webhook(self, request: Request, audio_path: str, camera_id: int, timestamp: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle audio file webhook - process sound detection"""
        from datetime import timedelta
        
        try:
            # Import sound detection service
            try:
                from ..services.sound_detection import sound_detection_service
                from ..database import SoundDetection
            except (ImportError, ValueError):
                from services.sound_detection import sound_detection_service
                from database import SoundDetection
            
            # Check if sound detection is available
            if not sound_detection_service.is_available():
                logger.info(f"Sound detection service not available, skipping audio file: {audio_path}")
                return {
                    "status": "skipped",
                    "message": "Sound detection service not available (librosa not installed)"
                }
            
            # Parse timestamp
            detection_timestamp = None
            if timestamp:
                try:
                    if isinstance(timestamp, str):
                        try:
                            detection_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            try:
                                detection_timestamp = datetime.fromtimestamp(float(timestamp))
                            except:
                                pass
                    elif isinstance(timestamp, (int, float)):
                        detection_timestamp = datetime.fromtimestamp(float(timestamp))
                except Exception as e:
                    logger.debug(f"Could not parse timestamp {timestamp}: {e}")
            
            if not detection_timestamp:
                detection_timestamp = datetime.now()
            
            # Process audio file for sound detection
            logger.info(f"Processing audio file for sound detection: {audio_path}")
            sound_results = sound_detection_service.detect_sounds(audio_path)
            
            if sound_results.get("error"):
                logger.warning(f"Sound detection error: {sound_results.get('error')}")
                return {
                    "status": "error",
                    "message": f"Sound detection failed: {sound_results.get('error')}"
                }
            
            # Find best sound classification (highest confidence)
            detected_sounds = sound_results.get("sounds", [])
            if not detected_sounds:
                logger.info(f"No sounds detected in {audio_path}")
                return {
                    "status": "skipped",
                    "message": "No sounds detected in audio file"
                }
            
            # Get the highest confidence sound classification
            best_sound = max(detected_sounds, key=lambda x: x.get("confidence", 0))
            sound_class = best_sound.get("sound_class", "unknown_sound")
            confidence = best_sound.get("confidence", 0.5)
            duration = sound_results.get("duration", 0)
            
            # Try to find a matching detection within a reasonable time window (e.g., 30 seconds)
            linked_detection_id = None
            try:
                time_window_start = detection_timestamp - timedelta(seconds=30)
                time_window_end = detection_timestamp + timedelta(seconds=30)
                
                recent_detection = self.db.query(Detection).filter(
                    Detection.camera_id == camera_id,
                    Detection.timestamp >= time_window_start,
                    Detection.timestamp <= time_window_end
                ).order_by(Detection.timestamp.desc()).first()
                
                if recent_detection:
                    linked_detection_id = recent_detection.id
                    logger.info(f"Linking sound detection to detection {linked_detection_id}")
            except Exception as e:
                logger.warning(f"Error finding linked detection: {e}")
            
            # Store audio features as JSON
            import json
            audio_features = {
                "all_sounds": detected_sounds,
                "sample_rate": sound_results.get("sample_rate"),
                "duration": duration
            }
            
            # Create sound detection record
            sound_detection = SoundDetection(
                camera_id=camera_id,
                detection_id=linked_detection_id,
                sound_class=sound_class,
                confidence=confidence,
                audio_path=audio_path,
                duration=duration,
                audio_features=json.dumps(audio_features),
                timestamp=detection_timestamp
            )
            
            self.db.add(sound_detection)
            self.db.commit()
            self.db.refresh(sound_detection)
            
            logger.info(f"Created sound detection {sound_detection.id}: {sound_class} (confidence: {confidence:.2f})")
            
            # Log audit event
            try:
                log_audit_event(
                    db=self.db,
                    request=request,
                    action="SOUND_DETECTED",
                    resource_type="sound_detection",
                    resource_id=sound_detection.id,
                    details={
                        "camera_id": camera_id,
                        "sound_class": sound_class,
                        "confidence": confidence,
                        "audio_path": audio_path,
                        "detection_id": linked_detection_id
                    }
                )
            except Exception as e:
                logger.warning(f"Error logging audit event: {e}")
            
            return {
                "status": "success",
                "message": f"Sound detection created: {sound_class}",
                "sound_detection_id": sound_detection.id,
                "sound_class": sound_class,
                "confidence": confidence,
                "detection_id": linked_detection_id
            }
            
        except Exception as e:
            logger.error(f"Error handling audio webhook: {e}", exc_info=True)
            self.db.rollback()
            return {
                "status": "error",
                "message": f"Error processing audio: {str(e)}"
            }