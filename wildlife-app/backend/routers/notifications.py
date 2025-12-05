"""Notification management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import logging

try:
    from ..utils.audit import log_audit_event
    from ..services.notifications import notification_service
except ImportError:
    from utils.audit import log_audit_event
    from services.notifications import notification_service

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_notifications_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup notifications router with rate limiting and dependencies"""
    
    @router.get("/api/notifications/status")
    def get_notification_status():
        """Get current notification enabled status"""
        return {
            "enabled": notification_service.enabled
        }

    @router.post("/api/notifications/toggle")
    @limiter.limit("10/minute")
    def toggle_notifications(request: Request, db: Session = Depends(get_db)):
        """Toggle notification enabled state"""
        try:
            new_state = notification_service.toggle()
            log_audit_event(
                db=db,
                request=request,
                action="UPDATE",
                resource_type="notification",
                details={
                    "enabled": new_state
                }
            )
            return {
                "enabled": new_state,
                "message": f"Notifications {'enabled' if new_state else 'disabled'}"
            }
        except Exception as e:
            logging.error(f"Error toggling notifications: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.put("/api/notifications/enabled")
    @limiter.limit("10/minute")
    def set_notification_enabled(request: Request, enabled: bool, db: Session = Depends(get_db)):
        """Set notification enabled state"""
        try:
            notification_service.enabled = enabled
            log_audit_event(
                db=db,
                request=request,
                action="UPDATE",
                resource_type="notification",
                details={
                    "enabled": enabled
                }
            )
            return {
                "enabled": notification_service.enabled,
                "message": f"Notifications {'enabled' if enabled else 'disabled'}"
            }
        except Exception as e:
            logging.error(f"Error setting notification state: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
