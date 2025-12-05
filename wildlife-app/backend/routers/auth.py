"""Authentication endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import Optional
import logging

try:
    from ..utils.audit import log_audit_event
except ImportError:
    from utils.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_auth_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup auth router with rate limiting and dependencies"""
    
    @router.post("/api/auth/register")
    @limiter.limit("5/hour")
    def register_user(
        request: Request,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "viewer",
        db: Session = Depends(get_db)
    ):
        """
        Register a new user
        
        Args:
            username: Username (must be unique)
            email: Email address (must be unique)
            password: Plain text password
            full_name: Optional full name
            role: User role (viewer, editor, admin) - default: viewer
        
        Returns:
            User information (without password)
        """
        try:
            from services.auth import auth_service
            
            user = auth_service.create_user(
                db=db,
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role=role
            )
            
            # Log registration
            log_audit_event(
                db=db,
                request=request,
                action="CREATE",
                resource_type="user",
                resource_id=user.id,
                details={
                    "username": username,
                    "email": email,
                    "role": role
                }
            )
            
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_superuser": user.is_superuser,
                "created_at": user.created_at.isoformat()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logging.error(f"Failed to register user: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")

    @router.post("/api/auth/login")
    @limiter.limit("10/minute")
    def login(
        request: Request,
        username: str,
        password: str,
        db: Session = Depends(get_db)
    ):
        """
        Login a user and create a session
        
        Args:
            username: Username or email
            password: Plain text password
        
        Returns:
            User information and session token
        """
        try:
            from services.auth import auth_service
            
            client_ip = get_remote_address(request)
            user_agent = request.headers.get("User-Agent")
            
            result = auth_service.authenticate_user(
                db=db,
                username=username,
                password=password,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            if not result:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            # Log successful login
            log_audit_event(
                db=db,
                request=request,
                action="LOGIN",
                resource_type="user",
                resource_id=result["user"]["id"],
                details={
                    "username": username,
                    "ip_address": client_ip
                }
            )
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Failed to login: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to login: {str(e)}")

    @router.post("/api/auth/logout")
    @limiter.limit("30/hour")
    def logout(
        request: Request,
        token: str,
        db: Session = Depends(get_db)
    ):
        """
        Logout a user by invalidating their session
        
        Args:
            token: Session token
        
        Returns:
            Success status
        """
        try:
            from services.auth import auth_service
            
            success = auth_service.logout(db, token)
            
            if not success:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Log logout
            log_audit_event(
                db=db,
                request=request,
                action="LOGOUT",
                resource_type="user",
                details={"token": token[:16] + "..."}  # Only log partial token
            )
            
            return {"success": True, "message": "Logged out successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Failed to logout: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to logout: {str(e)}")

    @router.get("/api/auth/me")
    @limiter.limit("60/minute")
    def get_current_user(
        request: Request,
        token: Optional[str] = Header(None, alias="Authorization"),
        db: Session = Depends(get_db)
    ):
        """
        Get current user information from session token
        
        Args:
            token: Session token (in Authorization header as "Bearer <token>" or just the token)
        
        Returns:
            Current user information
        """
        try:
            from services.auth import auth_service
            
            # Extract token from Authorization header
            if token and token.startswith("Bearer "):
                token = token.replace("Bearer ", "", 1)
            
            if not token:
                raise HTTPException(status_code=401, detail="No token provided")
            
            user = auth_service.verify_session(db, token)
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid or expired session")
            
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_superuser": user.is_superuser,
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Failed to get current user: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get current user: {str(e)}")

    @router.post("/api/auth/change-password")
    @limiter.limit("10/hour")
    def change_password(
        request: Request,
        old_password: str,
        new_password: str,
        token: Optional[str] = Header(None, alias="Authorization"),
        db: Session = Depends(get_db)
    ):
        """
        Change user password
        
        Args:
            old_password: Current password
            new_password: New password
            token: Session token
        
        Returns:
            Success status
        """
        try:
            from services.auth import auth_service
            
            # Extract token from Authorization header
            if token and token.startswith("Bearer "):
                token = token.replace("Bearer ", "", 1)
            
            if not token:
                raise HTTPException(status_code=401, detail="No token provided")
            
            user = auth_service.verify_session(db, token)
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid or expired session")
            
            success = auth_service.change_password(db, user.id, old_password, new_password)
            
            if not success:
                raise HTTPException(status_code=400, detail="Invalid old password")
            
            # Log password change
            log_audit_event(
                db=db,
                request=request,
                action="UPDATE",
                resource_type="user",
                resource_id=user.id,
                details={"action": "change_password"}
            )
            
            return {"success": True, "message": "Password changed successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Failed to change password: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")

    return router
