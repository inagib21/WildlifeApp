"""API key management service"""
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

try:
    from ..database import ApiKey
except ImportError:
    from database import ApiKey

logger = logging.getLogger(__name__)


class ApiKeyService:
    """Service for managing API keys"""
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        Hash an API key using SHA256
        
        Args:
            api_key: The API key to hash
        
        Returns:
            SHA256 hash of the key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new secure API key
        
        Returns:
            A secure random API key (32 bytes, base64 encoded)
        """
        # Generate 32 random bytes and encode as URL-safe base64
        return secrets.token_urlsafe(32)
    
    def create_key(
        self,
        db: Session,
        user_name: str,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        rate_limit_per_minute: int = 60,
        allowed_ips: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str]:
        """
        Create a new API key
        
        Args:
            db: Database session
            user_name: Name of the user/application
            description: Optional description
            expires_in_days: Optional expiration in days
            rate_limit_per_minute: Rate limit for this key
            allowed_ips: Optional list of allowed IP addresses
            metadata: Optional metadata dictionary
        
        Returns:
            Tuple of (api_key, key_hash) - store the api_key securely, it won't be shown again
        """
        # Generate new key
        api_key = self.generate_key()
        key_hash = self.hash_key(api_key)
        
        # Check if hash already exists (extremely unlikely but check anyway)
        existing = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if existing:
            # Regenerate if collision (extremely rare)
            api_key = self.generate_key()
            key_hash = self.hash_key(api_key)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key_record = ApiKey(
            key_hash=key_hash,
            user_name=user_name,
            description=description,
            is_active=True,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            allowed_ips=",".join(allowed_ips) if allowed_ips else None,
            extra_metadata=str(metadata) if metadata else None
        )
        
        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)
        
        logger.info(f"Created API key for user: {user_name} (ID: {api_key_record.id})")
        
        return api_key, key_hash
    
    def validate_key(
        self,
        db: Session,
        api_key: str,
        client_ip: Optional[str] = None
    ) -> Optional[ApiKey]:
        """
        Validate an API key
        
        Args:
            db: Database session
            api_key: The API key to validate
            client_ip: Optional client IP address for IP whitelist checking
        
        Returns:
            ApiKey record if valid, None otherwise
        """
        key_hash = self.hash_key(api_key)
        
        # Find key by hash
        api_key_record = db.query(ApiKey).filter(
            and_(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True
            )
        ).first()
        
        if not api_key_record:
            return None
        
        # Check expiration
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            logger.warning(f"API key expired: {api_key_record.id}")
            return None
        
        # Check IP whitelist if configured
        if api_key_record.allowed_ips and client_ip:
            allowed_ips = [ip.strip() for ip in api_key_record.allowed_ips.split(",")]
            if client_ip not in allowed_ips:
                logger.warning(f"API key access denied from IP: {client_ip} (not in whitelist)")
                return None
        
        # Update last used and usage count
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.usage_count += 1
        db.commit()
        
        return api_key_record
    
    def revoke_key(self, db: Session, key_id: int) -> bool:
        """
        Revoke an API key
        
        Args:
            db: Database session
            key_id: API key ID
        
        Returns:
            True if key was found and revoked, False otherwise
        """
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            return False
        
        api_key.is_active = False
        db.commit()
        
        logger.info(f"Revoked API key: {key_id}")
        return True
    
    def list_keys(
        self,
        db: Session,
        user_name: Optional[str] = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[ApiKey]:
        """
        List API keys with optional filtering
        
        Args:
            db: Database session
            user_name: Filter by user name
            active_only: Only return active keys
            limit: Maximum number of keys to return
            offset: Number of keys to skip
        
        Returns:
            List of ApiKey records
        """
        query = db.query(ApiKey)
        
        if user_name:
            query = query.filter(ApiKey.user_name == user_name)
        if active_only:
            query = query.filter(ApiKey.is_active == True)
        
        query = query.order_by(ApiKey.created_at.desc())
        
        return query.offset(offset).limit(limit).all()
    
    def get_key_stats(self, db: Session, key_id: int) -> Optional[Dict[str, Any]]:
        """
        Get statistics for an API key
        
        Args:
            db: Database session
            key_id: API key ID
        
        Returns:
            Dictionary with key statistics
        """
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            return None
        
        return {
            "id": api_key.id,
            "user_name": api_key.user_name,
            "description": api_key.description,
            "is_active": api_key.is_active,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
            "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "usage_count": api_key.usage_count,
            "rate_limit_per_minute": api_key.rate_limit_per_minute,
            "allowed_ips": api_key.allowed_ips.split(",") if api_key.allowed_ips else None,
            "is_expired": api_key.expires_at and api_key.expires_at < datetime.utcnow()
        }
    
    def rotate_key(
        self,
        db: Session,
        key_id: int,
        user_name: str,
        description: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Rotate an API key (create new, revoke old)
        
        Args:
            db: Database session
            key_id: Old API key ID to revoke
            user_name: User name for new key
            description: Optional description for new key
        
        Returns:
            Tuple of (new_api_key, new_key_hash)
        """
        # Revoke old key
        self.revoke_key(db, key_id)
        
        # Create new key
        return self.create_key(
            db=db,
            user_name=user_name,
            description=description or f"Rotated from key {key_id}"
        )


# Global instance
api_key_service = ApiKeyService()

