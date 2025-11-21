"""Audit logging utility for tracking system changes"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

try:
    from ..database import AuditLog
except ImportError:
    from database import AuditLog

logger = logging.getLogger(__name__)


def get_client_info(request: Request) -> Dict[str, Optional[str]]:
    """Extract client information from request"""
    # Get IP address (check for proxy headers)
    client_ip = request.client.host if request.client else None
    if request.headers.get("x-forwarded-for"):
        client_ip = request.headers.get("x-forwarded-for").split(",")[0].strip()
    elif request.headers.get("x-real-ip"):
        client_ip = request.headers.get("x-real-ip")
    
    return {
        "ip": client_ip,
        "user_agent": request.headers.get("user-agent"),
    }


def log_audit_event(
    db: Session,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    endpoint: Optional[str] = None
) -> None:
    """
    Log an audit event to the database
    
    Args:
        db: Database session
        request: FastAPI request object
        action: Action performed (CREATE, UPDATE, DELETE, SYNC, etc.)
        resource_type: Type of resource (camera, detection, motion_settings, etc.)
        resource_id: ID of the affected resource (if applicable)
        details: Additional details as a dictionary (will be JSON encoded)
        success: Whether the action succeeded
        error_message: Error message if action failed
        endpoint: API endpoint that was called (defaults to request.url.path)
    """
    try:
        client_info = get_client_info(request)
        
        audit_log = AuditLog(
            timestamp=datetime.utcnow(),
            action=action.upper(),
            resource_type=resource_type.lower(),
            resource_id=resource_id,
            user_ip=client_info["ip"],
            user_agent=client_info["user_agent"],
            endpoint=endpoint or str(request.url.path),
            details=json.dumps(details) if details else None,
            success=success,
            error_message=error_message
        )
        
        db.add(audit_log)
        db.commit()
    except Exception as e:
        # Don't fail the request if audit logging fails
        logger.error(f"Failed to log audit event: {e}", exc_info=True)
        db.rollback()


def get_audit_logs(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    success_only: bool = False
) -> list:
    """
    Retrieve audit logs with optional filtering
    
    Args:
        db: Database session
        limit: Maximum number of logs to return
        offset: Number of logs to skip
        action: Filter by action type
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        start_date: Filter logs after this date
        end_date: Filter logs before this date
        success_only: Only return successful actions
    
    Returns:
        List of audit log records
    """
    from sqlalchemy import and_
    
    query = db.query(AuditLog)
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type.lower())
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    if success_only:
        query = query.filter(AuditLog.success == True)
    
    # Order by most recent first
    query = query.order_by(AuditLog.timestamp.desc())
    
    # Apply pagination
    return query.offset(offset).limit(limit).all()

