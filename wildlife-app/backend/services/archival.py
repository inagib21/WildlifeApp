"""Image archival service for organizing and preserving important images"""
import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

try:
    from ..database import Detection, Camera
    from ..config import ARCHIVAL_ENABLED, ARCHIVAL_ROOT, ARCHIVAL_RULES
except ImportError:
    try:
        from database import Detection, Camera
        from config import ARCHIVAL_ENABLED, ARCHIVAL_ROOT, ARCHIVAL_RULES
    except ImportError:
        # Fallback if config doesn't have archival settings yet
        ARCHIVAL_ENABLED = False
        ARCHIVAL_ROOT = "./archived_photos"
        ARCHIVAL_RULES = {}

logger = logging.getLogger(__name__)


class ImageArchivalService:
    """Service for archiving images based on configurable rules"""
    
    def __init__(self, archival_root: Optional[str] = None):
        """
        Initialize archival service
        
        Args:
            archival_root: Root directory for archived images (default: ./archived_photos)
        """
        self.archival_root = Path(archival_root) if archival_root else Path("./archived_photos")
        self.archival_root.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.archival_root / "by_species").mkdir(exist_ok=True)
        (self.archival_root / "by_camera").mkdir(exist_ok=True)
        (self.archival_root / "by_date").mkdir(exist_ok=True)
        (self.archival_root / "high_confidence").mkdir(exist_ok=True)
    
    def should_archive(self, detection: Detection, rules: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Determine if a detection should be archived based on rules
        
        Args:
            detection: Detection record
            rules: Archival rules (if None, uses default rules)
        
        Returns:
            Tuple of (should_archive, reason)
        """
        if rules is None:
            rules = ARCHIVAL_RULES if hasattr(ARCHIVAL_RULES, '__getitem__') else {}
        
        # Default rules
        default_rules = {
            "min_confidence": 0.8,
            "min_age_days": 30,
            "archive_high_confidence": True,
            "archive_by_species": True,
            "archive_by_camera": True,
            "archive_by_date": True,
            "species_whitelist": None,  # None means all species
            "species_blacklist": []
        }
        
        # Merge with provided rules
        merged_rules = {**default_rules, **rules}
        
        # Check confidence threshold
        if detection.confidence and detection.confidence >= merged_rules["min_confidence"]:
            if merged_rules["archive_high_confidence"]:
                return True, f"High confidence ({detection.confidence:.2f})"
        
        # Check age threshold
        if detection.timestamp:
            age_days = (datetime.utcnow() - detection.timestamp).days
            if age_days >= merged_rules["min_age_days"]:
                return True, f"Age threshold ({age_days} days)"
        
        # Check species whitelist/blacklist
        if detection.species:
            species = detection.species.lower()
            
            # Check blacklist
            blacklist = [s.lower() for s in merged_rules.get("species_blacklist", [])]
            if species in blacklist:
                return False, "Species in blacklist"
            
            # Check whitelist
            whitelist = merged_rules.get("species_whitelist")
            if whitelist:
                whitelist_lower = [s.lower() for s in whitelist]
                if species in whitelist_lower:
                    return True, f"Species in whitelist ({detection.species})"
        
        return False, "No matching rules"
    
    def archive_image(self, detection: Detection, db: Session, rules: Optional[Dict] = None) -> Optional[str]:
        """
        Archive an image for a detection
        
        Args:
            detection: Detection record
            db: Database session
            rules: Archival rules
        
        Returns:
            Path to archived image, or None if archiving failed
        """
        if not detection.image_path or not os.path.exists(detection.image_path):
            logger.warning(f"Image path does not exist: {detection.image_path}")
            return None
        
        should_archive, reason = self.should_archive(detection, rules)
        if not should_archive:
            logger.debug(f"Skipping archival for detection {detection.id}: {reason}")
            return None
        
        try:
            # Determine archival subdirectory
            subdirs = []
            
            if rules is None:
                rules = ARCHIVAL_RULES if hasattr(ARCHIVAL_RULES, '__getitem__') else {}
            
            default_rules = {
                "archive_by_species": True,
                "archive_by_camera": True,
                "archive_by_date": True,
                "archive_high_confidence": True
            }
            merged_rules = {**default_rules, **rules}
            
            # Archive by species
            if merged_rules.get("archive_by_species") and detection.species:
                species_dir = detection.species.lower().replace(" ", "_")
                subdirs.append(("by_species", species_dir))
            
            # Archive by camera
            if merged_rules.get("archive_by_camera") and detection.camera_id:
                camera = db.query(Camera).filter(Camera.id == detection.camera_id).first()
                if camera:
                    camera_dir = camera.name.lower().replace(" ", "_")
                    subdirs.append(("by_camera", camera_dir))
            
            # Archive by date
            if merged_rules.get("archive_by_date") and detection.timestamp:
                date_dir = detection.timestamp.strftime("%Y-%m")
                subdirs.append(("by_date", date_dir))
            
            # Archive high confidence separately
            if merged_rules.get("archive_high_confidence") and detection.confidence and detection.confidence >= 0.8:
                subdirs.append(("high_confidence", None))
            
            # Create destination path (use first subdirectory strategy)
            if subdirs:
                strategy, subdir = subdirs[0]
                dest_dir = self.archival_root / strategy
                if subdir:
                    dest_dir = dest_dir / subdir
                dest_dir.mkdir(parents=True, exist_ok=True)
            else:
                dest_dir = self.archival_root
            
            # Generate unique filename
            source_path = Path(detection.image_path)
            timestamp_str = detection.timestamp.strftime("%Y%m%d_%H%M%S") if detection.timestamp else datetime.now().strftime("%Y%m%d_%H%M%S")
            camera_id_str = f"cam{detection.camera_id}" if detection.camera_id else "unknown"
            species_str = detection.species.lower().replace(" ", "_") if detection.species else "unknown"
            filename = f"{timestamp_str}_{camera_id_str}_{species_str}_{detection.id}{source_path.suffix}"
            
            dest_path = dest_dir / filename
            
            # Copy file (don't move, keep original)
            shutil.copy2(source_path, dest_path)
            
            logger.info(f"Archived image for detection {detection.id} to {dest_path} (reason: {reason})")
            
            # Update detection with archival path (optional - add field to model if needed)
            # For now, we'll just return the path
            
            return str(dest_path)
        
        except Exception as e:
            logger.error(f"Failed to archive image for detection {detection.id}: {e}", exc_info=True)
            return None
    
    def archive_detections(self, db: Session, limit: int = 100, rules: Optional[Dict] = None) -> Dict[str, int]:
        """
        Archive multiple detections based on rules
        
        Args:
            db: Database session
            limit: Maximum number of detections to process
            rules: Archival rules
        
        Returns:
            Dictionary with archival statistics
        """
        stats = {
            "processed": 0,
            "archived": 0,
            "skipped": 0,
            "errors": 0
        }
        
        try:
            # Get detections that haven't been archived yet
            # For now, we'll process all detections (you can add an 'archived' flag to Detection model)
            detections = db.query(Detection).filter(
                Detection.image_path.isnot(None)
            ).limit(limit).all()
            
            for detection in detections:
                stats["processed"] += 1
                
                try:
                    archived_path = self.archive_image(detection, db, rules)
                    if archived_path:
                        stats["archived"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.error(f"Error archiving detection {detection.id}: {e}")
                    stats["errors"] += 1
            
            logger.info(f"Archival batch complete: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"Failed to archive detections: {e}", exc_info=True)
            stats["errors"] = stats["processed"]
            return stats
    
    def get_archival_stats(self) -> Dict[str, any]:
        """
        Get statistics about archived images
        
        Returns:
            Dictionary with archival statistics
        """
        stats = {
            "total_archived": 0,
            "by_species": {},
            "by_camera": {},
            "by_date": {},
            "high_confidence_count": 0,
            "total_size_gb": 0.0
        }
        
        try:
            # Count files in each directory
            for strategy_dir in ["by_species", "by_camera", "by_date", "high_confidence"]:
                strategy_path = self.archival_root / strategy_dir
                if strategy_dir == "high_confidence":
                    # Count files directly in high_confidence
                    if strategy_path.exists():
                        files = list(strategy_path.glob("*.*"))
                        stats["high_confidence_count"] = len([f for f in files if f.is_file()])
                        stats["total_archived"] += stats["high_confidence_count"]
                else:
                    # Count files in subdirectories
                    if strategy_path.exists():
                        for subdir in strategy_dir.iterdir() if hasattr(strategy_dir, 'iterdir') else []:
                            if subdir.is_dir():
                                files = list(subdir.glob("*.*"))
                                file_count = len([f for f in files if f.is_file()])
                                
                                if strategy_dir == "by_species":
                                    stats["by_species"][subdir.name] = file_count
                                elif strategy_dir == "by_camera":
                                    stats["by_camera"][subdir.name] = file_count
                                elif strategy_dir == "by_date":
                                    stats["by_date"][subdir.name] = file_count
                                
                                stats["total_archived"] += file_count
            
            # Calculate total size
            total_size = 0
            for root, dirs, files in os.walk(self.archival_root):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass
            
            stats["total_size_gb"] = round(total_size / (1024**3), 2)
            
        except Exception as e:
            logger.error(f"Failed to get archival stats: {e}", exc_info=True)
        
        return stats
    
    def cleanup_old_archives(self, max_age_days: int = 365, dry_run: bool = False) -> Dict[str, int]:
        """
        Clean up old archived images
        
        Args:
            max_age_days: Maximum age in days before deletion
            dry_run: If True, only report what would be deleted
        
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "checked": 0,
            "deleted": 0,
            "errors": 0,
            "freed_gb": 0.0
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            freed_size = 0
            
            for root, dirs, files in os.walk(self.archival_root):
                for file in files:
                    file_path = Path(root) / file
                    stats["checked"] += 1
                    
                    try:
                        # Check file modification time
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        
                        if mtime < cutoff_date:
                            file_size = file_path.stat().st_size
                            
                            if not dry_run:
                                file_path.unlink()
                                freed_size += file_size
                                stats["deleted"] += 1
                            else:
                                stats["deleted"] += 1
                                freed_size += file_size
                    
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        stats["errors"] += 1
            
            stats["freed_gb"] = round(freed_size / (1024**3), 2)
            
            logger.info(f"Cleanup complete: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"Failed to cleanup old archives: {e}", exc_info=True)
            return stats


# Global instance
archival_service = ImageArchivalService()

