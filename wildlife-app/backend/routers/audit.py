"""Audit log endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

try:
    from ..models import AuditLogResponse
    from ..utils.audit import get_audit_logs
except ImportError:
    from models import AuditLogResponse
    from utils.audit import get_audit_logs

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_audit_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup audit router with rate limiting and dependencies"""
    
    @router.get("/audit-logs", response_model=List[AuditLogResponse])
    @limiter.limit("60/minute")  # Rate limit: 60 requests per minute
    def get_audit_logs_endpoint(
        request: Request,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        success_only: bool = False,
        db: Session = Depends(get_db)
    ):
        """Get audit logs with optional filtering"""
        # Optional date filtering (last 30 days by default if not specified)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        logs = get_audit_logs(
            db=db,
            limit=limit,
            offset=offset,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            success_only=success_only
        )
        
        return logs

    @router.get("/api/audit-logs", response_model=List[AuditLogResponse])
    @limiter.limit("60/minute")  # Rate limit: 60 requests per minute
    def get_audit_logs_api(
        request: Request,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        success_only: bool = False,
        db: Session = Depends(get_db)
    ):
        """API endpoint alias for audit logs"""
        return get_audit_logs_endpoint(request, limit, offset, action, resource_type, resource_id, success_only, db)

    return router

