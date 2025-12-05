"""Configuration management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import Dict
import logging

try:
    from ..utils.audit import log_audit_event
except ImportError:
    from utils.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_config_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup config router with rate limiting and dependencies"""
    
    @router.get("/api/config")
    @limiter.limit("60/minute")
    def get_config(request: Request):
        """Get current configuration values (read-only, for UI display)"""
        try:
            from config import (
                DB_HOST, DB_PORT, DB_NAME, MOTIONEYE_URL, SPECIESNET_URL,
                NOTIFICATION_ENABLED, SMTP_HOST, SMTP_PORT, SMTP_USER,
                NOTIFICATION_EMAIL_FROM, NOTIFICATION_EMAIL_TO,
                SMS_ENABLED, TWILIO_ACCOUNT_SID, TWILIO_PHONE_NUMBER,
                BACKUP_SCHEDULE_MONTHLY_DAY, BACKUP_SCHEDULE_MONTHLY_HOUR,
                BACKUP_RETENTION_COUNT,
                ARCHIVAL_ENABLED, ARCHIVAL_ROOT, ARCHIVAL_RULES,
                API_KEY_ENABLED, SESSION_EXPIRY_HOURS
            )
            
            # Return config values (mask sensitive data)
            return {
                "DB_HOST": DB_HOST,
                "DB_PORT": DB_PORT,
                "DB_NAME": DB_NAME,
                "MOTIONEYE_URL": MOTIONEYE_URL,
                "SPECIESNET_URL": SPECIESNET_URL,
                "NOTIFICATION_ENABLED": str(NOTIFICATION_ENABLED).lower(),
                "SMTP_HOST": SMTP_HOST,
                "SMTP_PORT": str(SMTP_PORT),
                "SMTP_USER": SMTP_USER if SMTP_USER else "",
                "NOTIFICATION_EMAIL_FROM": NOTIFICATION_EMAIL_FROM if NOTIFICATION_EMAIL_FROM else "",
                "NOTIFICATION_EMAIL_TO": NOTIFICATION_EMAIL_TO if NOTIFICATION_EMAIL_TO else "",
                "SMS_ENABLED": str(SMS_ENABLED).lower(),
                "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID and len(TWILIO_ACCOUNT_SID) > 10 else "",
                "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER if TWILIO_PHONE_NUMBER else "",
                "BACKUP_SCHEDULE_MONTHLY_DAY": str(BACKUP_SCHEDULE_MONTHLY_DAY),
                "BACKUP_SCHEDULE_MONTHLY_HOUR": str(BACKUP_SCHEDULE_MONTHLY_HOUR),
                "BACKUP_RETENTION_COUNT": str(BACKUP_RETENTION_COUNT),
                "ARCHIVAL_ENABLED": str(ARCHIVAL_ENABLED).lower(),
                "ARCHIVAL_ROOT": ARCHIVAL_ROOT,
                "ARCHIVAL_MIN_CONFIDENCE": str(ARCHIVAL_RULES.get("min_confidence", 0.8)),
                "ARCHIVAL_MIN_AGE_DAYS": str(ARCHIVAL_RULES.get("min_age_days", 30)),
                "API_KEY_ENABLED": str(API_KEY_ENABLED).lower(),
                "SESSION_EXPIRY_HOURS": str(SESSION_EXPIRY_HOURS),
                "note": "Configuration changes require editing .env file and restarting the server"
            }
        except Exception as e:
            logging.error(f"Failed to get config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

    @router.post("/api/config")
    @limiter.limit("10/hour")
    def update_config(request: Request, configs: Dict[str, str], db: Session = Depends(get_db)):
        """Update configuration (note: actual changes require .env file modification)"""
        try:
            # Log the attempt
            log_audit_event(
                db=db,
                request=request,
                action="CONFIG_UPDATE",
                resource_type="configuration",
                details={
                    "keys_updated": list(configs.keys()),
                    "note": "Configuration UI is read-only. Changes require .env file modification."
                }
            )
            
            return {
                "success": True,
                "message": "Configuration UI is for viewing only. To change settings, edit the .env file and restart the server.",
                "note": "See ENV_SETUP.md for configuration instructions"
            }
        except Exception as e:
            logging.error(f"Failed to update config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

    return router
