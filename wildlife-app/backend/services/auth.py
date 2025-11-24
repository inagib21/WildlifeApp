"""Authentication and authorization service"""
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

try:
    from ..database import User, Session as SessionModel
    from ..config import JWT_SECRET_KEY, JWT_ALGORITHM, SESSION_EXPIRY_HOURS
except ImportError:
    from database import User, Session as SessionModel
    from config import JWT_SECRET_KEY, JWT_ALGORITHM, SESSION_EXPIRY_HOURS

logger = logging.getLogger(__name__)

try:
    import bcrypt
    from jose import JWTError, jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("JWT libraries not available. Install python-jose[cryptography] and bcrypt")


class AuthService:
    """Service for user authentication and authorization"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password
        """
        if not JWT_AVAILABLE:
            raise RuntimeError("bcrypt not available. Install bcrypt package.")
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
        
        Returns:
            True if password matches, False otherwise
        """
        if not JWT_AVAILABLE:
            raise RuntimeError("bcrypt not available. Install bcrypt package.")
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False
    
    @staticmethod
    def generate_session_token() -> str:
        """
        Generate a secure session token
        
        Returns:
            Random session token
        """
        return secrets.token_urlsafe(32)
    
    def create_user(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "viewer",
        is_superuser: bool = False
    ) -> User:
        """
        Create a new user
        
        Args:
            db: Database session
            username: Username
            email: Email address
            password: Plain text password
            full_name: Optional full name
            role: User role (viewer, editor, admin)
            is_superuser: Whether user is a superuser
        
        Returns:
            Created User object
        """
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            raise ValueError(f"User with username '{username}' or email '{email}' already exists")
        
        # Hash password
        hashed_password = self.hash_password(password)
        
        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_superuser=is_superuser,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Created user: {username} (ID: {user.id})")
        return user
    
    def authenticate_user(
        self,
        db: Session,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user and create a session
        
        Args:
            db: Database session
            username: Username or email
            password: Plain text password
            ip_address: Optional IP address
            user_agent: Optional user agent
        
        Returns:
            Dictionary with user info and session token, or None if authentication failed
        """
        # Find user by username or email
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            logger.warning(f"Authentication failed: User '{username}' not found")
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            logger.warning(f"Authentication failed: Account '{username}' is locked until {user.locked_until}")
            return None
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Authentication failed: Account '{username}' is inactive")
            return None
        
        # Verify password
        if not self.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts (lock for 30 minutes)
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                logger.warning(f"Account '{username}' locked due to too many failed login attempts")
            
            db.commit()
            logger.warning(f"Authentication failed: Invalid password for user '{username}'")
            return None
        
        # Reset failed login attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create session
        session_token = self.generate_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        
        session = SessionModel(
            user_id=user.id,
            token=session_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(session)
        db.commit()
        
        logger.info(f"User '{username}' authenticated successfully (Session ID: {session.id})")
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_superuser": user.is_superuser
            },
            "token": session_token,
            "expires_at": expires_at.isoformat()
        }
    
    def verify_session(
        self,
        db: Session,
        token: str
    ) -> Optional[User]:
        """
        Verify a session token and return the user
        
        Args:
            db: Database session
            token: Session token
        
        Returns:
            User object if session is valid, None otherwise
        """
        session = db.query(SessionModel).filter(
            and_(
                SessionModel.token == token,
                SessionModel.is_active == True,
                SessionModel.expires_at > datetime.utcnow()
            )
        ).first()
        
        if not session:
            return None
        
        # Update last used timestamp
        session.last_used_at = datetime.utcnow()
        db.commit()
        
        # Get user
        user = db.query(User).filter(User.id == session.user_id).first()
        
        if not user or not user.is_active:
            # Invalidate session if user is inactive
            session.is_active = False
            db.commit()
            return None
        
        return user
    
    def logout(self, db: Session, token: str) -> bool:
        """
        Logout a user by invalidating their session
        
        Args:
            db: Database session
            token: Session token
        
        Returns:
            True if session was found and invalidated, False otherwise
        """
        session = db.query(SessionModel).filter(SessionModel.token == token).first()
        
        if not session:
            return False
        
        session.is_active = False
        db.commit()
        
        logger.info(f"User logged out (Session ID: {session.id})")
        return True
    
    def has_permission(self, user: User, resource: str, action: str) -> bool:
        """
        Check if user has permission to perform an action on a resource
        
        Args:
            user: User object
            resource: Resource type (e.g., 'camera', 'detection', 'user')
            action: Action (e.g., 'create', 'update', 'delete', 'view')
        
        Returns:
            True if user has permission, False otherwise
        """
        # Superusers have all permissions
        if user.is_superuser:
            return True
        
        # Define permissions by role
        permissions = {
            "viewer": {
                "camera": ["view"],
                "detection": ["view"],
                "user": [],
                "system": ["view"]
            },
            "editor": {
                "camera": ["view", "create", "update"],
                "detection": ["view", "create", "update", "delete"],
                "user": [],
                "system": ["view"]
            },
            "admin": {
                "camera": ["view", "create", "update", "delete"],
                "detection": ["view", "create", "update", "delete"],
                "user": ["view", "create", "update"],
                "system": ["view", "update"]
            }
        }
        
        role_perms = permissions.get(user.role, {})
        resource_perms = role_perms.get(resource, [])
        
        return action in resource_perms
    
    def change_password(
        self,
        db: Session,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change a user's password
        
        Args:
            db: Database session
            user_id: User ID
            old_password: Current password
            new_password: New password
        
        Returns:
            True if password was changed, False otherwise
        """
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return False
        
        # Verify old password
        if not self.verify_password(old_password, user.hashed_password):
            return False
        
        # Set new password
        user.hashed_password = self.hash_password(new_password)
        db.commit()
        
        logger.info(f"Password changed for user ID: {user_id}")
        return True


# Global instance
auth_service = AuthService()

