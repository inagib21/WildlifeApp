"""Backup management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import logging

try:
    from ..utils.audit import log_audit_event
except ImportError:
    from utils.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_backups_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup backups router with rate limiting and dependencies"""
    
    @router.post("/api/backup/create")
    @limiter.limit("5/hour")  # Rate limit: 5 backups per hour
    def create_backup_endpoint(request: Request, db: Session = Depends(get_db)):
        """Manually trigger a database backup"""
        try:
            from services.backup import backup_service
            
            backup_path = backup_service.create_backup()
            
            if backup_path:
                # Log backup creation
                log_audit_event(
                    db=db,
                    request=request,
                    action="BACKUP",
                    resource_type="database",
                    details={
                        "backup_path": str(backup_path),
                        "size_mb": round(backup_path.stat().st_size / (1024 * 1024), 2)
                    }
                )
                
                return {
                    "success": True,
                    "backup_path": str(backup_path),
                    "size_mb": round(backup_path.stat().st_size / (1024 * 1024), 2),
                    "message": "Backup created successfully"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to create backup")
                
        except Exception as e:
            logging.error(f"Backup creation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

    @router.get("/api/backup/list")
    @limiter.limit("60/minute")
    def list_backups_endpoint(request: Request):
        """List all available backups"""
        try:
            from services.backup import backup_service
            
            backups = backup_service.list_backups()
            backup_info = []
            
            for backup in backups:
                info = backup_service.get_backup_info(backup)
                if info:
                    backup_info.append(info)
            
            return {
                "backups": backup_info,
                "count": len(backup_info)
            }
        except Exception as e:
            logging.error(f"Failed to list backups: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")

    @router.post("/api/backup/cleanup")
    @limiter.limit("5/hour")
    def cleanup_backups_endpoint(request: Request, keep_count: int = 10, db: Session = Depends(get_db)):
        """Clean up old backups, keeping only the most recent N"""
        try:
            from services.backup import backup_service
            
            deleted_count = backup_service.cleanup_old_backups(keep_count=keep_count)
            
            # Log cleanup
            log_audit_event(
                db=db,
                request=request,
                action="CLEANUP",
                resource_type="backup",
                details={
                    "deleted_count": deleted_count,
                    "keep_count": keep_count
                }
            )
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "keep_count": keep_count,
                "message": f"Cleaned up {deleted_count} old backup(s)"
            }
        except Exception as e:
            logging.error(f"Backup cleanup failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

    return router
