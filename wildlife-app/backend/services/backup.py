"""Automated database backup service"""
import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from ..config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL
except ImportError:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATABASE_URL

logger = logging.getLogger(__name__)


class BackupService:
    """Service for automated database backups"""
    
    def __init__(self, backup_dir: Optional[str] = None):
        """
        Initialize backup service
        
        Args:
            backup_dir: Directory to store backups (defaults to ./backups)
        """
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            # Default to ./backups relative to backend directory
            backend_dir = Path(__file__).parent.parent
            self.backup_dir = backend_dir / "backups"
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_host = DB_HOST
        self.db_port = DB_PORT
        self.db_name = DB_NAME
        self.db_user = DB_USER
        self.db_password = DB_PASSWORD
    
    def create_backup(self, filename: Optional[str] = None) -> Optional[Path]:
        """
        Create a database backup using pg_dump
        
        Args:
            filename: Optional custom filename (defaults to timestamp-based name)
        
        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"wildlife_backup_{timestamp}.sql"
            
            backup_path = self.backup_dir / filename
            
            # Build pg_dump command
            # Use PGPASSWORD environment variable for password (more secure than command line)
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            cmd = [
                'pg_dump',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', self.db_name,
                '-F', 'c',  # Custom format (compressed)
                '-f', str(backup_path)
            ]
            
            logger.info(f"Creating database backup: {backup_path}")
            
            # Run pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            if backup_path.exists() and backup_path.stat().st_size > 0:
                file_size_mb = backup_path.stat().st_size / (1024 * 1024)
                logger.info(f"Backup created successfully: {backup_path} ({file_size_mb:.2f} MB)")
                return backup_path
            else:
                logger.error(f"Backup file was not created or is empty: {backup_path}")
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"pg_dump failed: {e.stderr}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Failed to create backup: {e}", exc_info=True)
            return None
    
    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore database from backup file
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            True if restore successful, False otherwise
        """
        try:
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            logger.warning(f"Restoring database from backup: {backup_path}")
            logger.warning("This will overwrite the current database!")
            
            # Build pg_restore command
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            cmd = [
                'pg_restore',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', self.db_name,
                '--clean',  # Clean before restore
                '--if-exists',  # Don't error if objects don't exist
                str(backup_path)
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Database restored successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"pg_restore failed: {e.stderr}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}", exc_info=True)
            return False
    
    def list_backups(self) -> list[Path]:
        """
        List all backup files in backup directory
        
        Returns:
            List of backup file paths, sorted by modification time (newest first)
        """
        backups = list(self.backup_dir.glob("wildlife_backup_*.sql"))
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Delete old backup files, keeping only the most recent N backups
        
        Args:
            keep_count: Number of recent backups to keep
        
        Returns:
            Number of backups deleted
        """
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return 0
        
        # Delete oldest backups
        to_delete = backups[keep_count:]
        deleted_count = 0
        
        for backup in to_delete:
            try:
                backup.unlink()
                deleted_count += 1
                logger.info(f"Deleted old backup: {backup}")
            except Exception as e:
                logger.error(f"Failed to delete backup {backup}: {e}")
        
        return deleted_count
    
    def get_backup_info(self, backup_path: Path) -> Optional[dict]:
        """
        Get information about a backup file
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            Dictionary with backup info or None if file doesn't exist
        """
        if not backup_path.exists():
            return None
        
        stat = backup_path.stat()
        return {
            "filename": backup_path.name,
            "path": str(backup_path),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }


# Global backup service instance
backup_service = BackupService()

