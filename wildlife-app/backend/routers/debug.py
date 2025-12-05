"""Debug endpoints for troubleshooting"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
import os
import logging

try:
    from ..services.events import get_event_manager
    from ..services.photo_scanner import PhotoScanner
    from ..utils.audit import log_audit_event, get_audit_logs
    from ..database import AuditLog
    from datetime import datetime, timedelta
except ImportError:
    from services.events import get_event_manager
    from services.photo_scanner import PhotoScanner
    from utils.audit import log_audit_event, get_audit_logs
    from database import AuditLog
    from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_debug_router(get_db) -> APIRouter:
    """Setup debug router for troubleshooting endpoints"""
    
    event_manager = get_event_manager()
    
    @router.get("/api/debug/file-system")
    def debug_file_system():
        """Debug endpoint to check file system structure"""
        try:
            current_dir = os.getcwd()
            
            # Check if archived_photos directory exists
            archived_photos_path = os.path.join(current_dir, "archived_photos")
            archived_photos_exists = os.path.exists(archived_photos_path)
            
            # Check if motioneye_media directory exists
            motioneye_media_path = os.path.join(current_dir, "motioneye_media")
            motioneye_media_exists = os.path.exists(motioneye_media_path)
            
            # List contents of archived_photos if it exists
            archived_contents = []
            if archived_photos_exists:
                try:
                    for species in os.listdir(archived_photos_path):
                        species_path = os.path.join(archived_photos_path, species)
                        if os.path.isdir(species_path):
                            cameras = []
                            for camera in os.listdir(species_path):
                                camera_path = os.path.join(species_path, camera)
                                if os.path.isdir(camera_path):
                                    dates = []
                                    for date in os.listdir(camera_path):
                                        date_path = os.path.join(camera_path, date)
                                        if os.path.isdir(date_path):
                                            files = os.listdir(date_path)
                                            dates.append({"date": date, "file_count": len(files)})
                                    cameras.append({"camera": camera, "dates": dates})
                            archived_contents.append({"species": species, "cameras": cameras})
                except Exception as e:
                    archived_contents = [{"error": str(e)}]
            
            return {
                "current_working_directory": current_dir,
                "archived_photos": {
                    "exists": archived_photos_exists,
                    "path": archived_photos_path,
                    "contents": archived_contents
                },
                "motioneye_media": {
                    "exists": motioneye_media_exists,
                    "path": motioneye_media_path
                }
            }
        except Exception as e:
            return {"error": str(e)}

    @router.get("/api/trigger-photo-scan")
    async def trigger_photo_scan(request: Request, db: Session = Depends(get_db)):
        """Manually trigger photo scanner to process unprocessed photos"""
        try:
            scanner = PhotoScanner(db, event_manager=event_manager)
            await scanner.scan_and_process()
            
            # Log successful scan trigger
            log_audit_event(
                db=db,
                request=request,
                action="TRIGGER",
                resource_type="photo_scan",
                details={"triggered_by": "manual"}
            )
            
            return {"message": "Photo scan completed successfully"}
        except Exception as e:
            # Log failed scan trigger
            log_audit_event(
                db=db,
                request=request,
                action="TRIGGER",
                resource_type="photo_scan",
                success=False,
                error_message=str(e)
            )
            raise HTTPException(status_code=500, detail=f"Photo scan failed: {str(e)}")

    @router.get("/api/photo-scan-status")
    async def get_photo_scan_status(db: Session = Depends(get_db)):
        """Get status of photo scanner and statistics"""
        try:
            scanner = PhotoScanner(db, event_manager=event_manager)
            
            # Load current processed files
            scanner.load_processed_files()
            
            # Scan for unprocessed photos
            unprocessed = scanner.scan_for_unprocessed_photos()
            
            # Count total photos in media folders
            total_photos = 0
            if os.path.exists(scanner.media_root):
                for camera_folder in os.listdir(scanner.media_root):
                    camera_path = os.path.join(scanner.media_root, camera_folder)
                    if not os.path.isdir(camera_path):
                        continue
                        
                    for date_folder in os.listdir(camera_path):
                        date_path = os.path.join(camera_path, date_folder)
                        if not os.path.isdir(date_path) or len(date_folder) != 10:
                            continue
                        
                        for filename in os.listdir(date_path):
                            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                                total_photos += 1
            
            processed_count = len(scanner.processed_files)
            unprocessed_count = len(unprocessed)
            
            return {
                "total_photos": total_photos,
                "processed_photos": processed_count,
                "unprocessed_photos": unprocessed_count,
                "last_scan": "Background scanner runs every 15 minutes",
                "scanner_active": True
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get scan status: {str(e)}")

    @router.get("/api/debug/error-statistics")
    def get_error_statistics(db: Session = Depends(get_db), hours: int = 24):
        """Get error statistics from audit logs"""
        try:
            import json
            
            # Get time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            # Query error logs
            error_logs = db.query(AuditLog).filter(
                AuditLog.timestamp >= start_time,
                AuditLog.timestamp <= end_time,
                AuditLog.success == False
            ).all()
            
            # Categorize errors
            error_categories = {}
            error_types = {}
            error_by_action = {}
            recent_errors = []
            
            for log in error_logs:
                # Parse details if available
                details = {}
                if log.details:
                    try:
                        details = json.loads(log.details) if isinstance(log.details, str) else log.details
                    except:
                        pass
                
                # Count by category
                category = details.get("error_category", "unknown")
                error_categories[category] = error_categories.get(category, 0) + 1
                
                # Count by error type
                error_type = details.get("error_type", log.error_message or "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
                
                # Count by action
                action = log.action
                error_by_action[action] = error_by_action.get(action, 0) + 1
                
                # Collect recent errors
                recent_errors.append({
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "action": action,
                    "error_type": error_type,
                    "error_category": category,
                    "error_message": log.error_message,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "suggestion": details.get("suggestion", "Check logs for details")
                })
            
            # Sort recent errors by timestamp (newest first)
            recent_errors.sort(key=lambda x: x["timestamp"] or "", reverse=True)
            
            # Get webhook-specific errors
            webhook_errors = [e for e in recent_errors if "WEBHOOK" in e["action"]]
            
            return {
                "time_range_hours": hours,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_errors": len(error_logs),
                "error_categories": dict(sorted(error_categories.items(), key=lambda x: x[1], reverse=True)),
                "error_types": dict(sorted(error_types.items(), key=lambda x: x[1], reverse=True)),
                "error_by_action": dict(sorted(error_by_action.items(), key=lambda x: x[1], reverse=True)),
                "webhook_errors": {
                    "total": len(webhook_errors),
                    "recent": webhook_errors[:10]  # Last 10 webhook errors
                },
                "recent_errors": recent_errors[:20],  # Last 20 errors overall
                "most_common_category": max(error_categories.items(), key=lambda x: x[1])[0] if error_categories else None,
                "most_common_type": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get error statistics: {str(e)}")

    return router

