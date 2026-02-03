"""Auto-zip service for compressing old images"""
import os
import logging
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

try:
    from ..database import Detection
    from ..routers.settings import get_setting
except ImportError:
    from database import Detection
    from routers.settings import get_setting

logger = logging.getLogger(__name__)


class AutoZipService:
    """Service for automatically zipping old images"""
    
    def __init__(self):
        self.archive_root = "./archived_photos"
        self.zip_root = "./archived_photos/zipped"
    
    def get_config(self, db: Session) -> Dict[str, Any]:
        """Get auto-zip configuration from settings"""
        enabled = get_setting(db, "auto_zip_enabled", default=False)
        retention_months = get_setting(db, "auto_zip_retention_months", default=3)
        return {
            "enabled": bool(enabled),
            "retention_months": int(retention_months)
        }
    
    def should_zip_image(self, detection: Detection, retention_months: int) -> bool:
        """Check if an image should be zipped based on age"""
        if not detection.timestamp:
            return False
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_months * 30)
        return detection.timestamp < cutoff_date
    
    def zip_images(
        self,
        db: Session,
        retention_months: int = 3,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Zip images older than retention_months
        
        Args:
            db: Database session
            retention_months: Number of months before images are zipped
            dry_run: If True, don't actually zip, just report what would be zipped
        
        Returns:
            Dictionary with zip operation results
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_months * 30)
        
        # Find detections older than cutoff
        old_detections = db.query(Detection).filter(
            Detection.timestamp < cutoff_date,
            Detection.image_path.isnot(None)
        ).all()
        
        if not old_detections:
            return {
                "zipped": 0,
                "skipped": 0,
                "errors": 0,
                "message": "No images to zip"
            }
        
        # Group by month for organized zipping
        zipped_count = 0
        skipped_count = 0
        error_count = 0
        zip_files_created = []
        
        # Create zip root directory
        zip_root = Path(self.zip_root)
        if not dry_run:
            zip_root.mkdir(parents=True, exist_ok=True)
        
        # Group detections by year-month
        detections_by_month = {}
        for det in old_detections:
            if not det.image_path or not os.path.exists(det.image_path):
                skipped_count += 1
                continue
            
            # Get year-month key
            year_month = det.timestamp.strftime("%Y-%m")
            if year_month not in detections_by_month:
                detections_by_month[year_month] = []
            detections_by_month[year_month].append(det)
        
        # Create zip files for each month
        for year_month, detections in detections_by_month.items():
            zip_filename = f"detections_{year_month}.zip"
            zip_path = zip_root / zip_filename
            
            if not dry_run:
                try:
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for det in detections:
                            try:
                                image_path = Path(det.image_path)
                                if image_path.exists():
                                    # Add to zip with relative path
                                    zip_file.write(image_path, image_path.name)
                                    zipped_count += 1
                                    
                                    # Optionally delete original after zipping
                                    # Uncomment if you want to delete originals:
                                    # image_path.unlink()
                                else:
                                    skipped_count += 1
                            except Exception as e:
                                logger.error(f"Error adding {det.image_path} to zip: {e}")
                                error_count += 1
                    
                    zip_files_created.append(str(zip_path))
                    logger.info(f"Created zip file: {zip_path} with {len(detections)} images")
                    
                except Exception as e:
                    logger.error(f"Error creating zip file {zip_path}: {e}")
                    error_count += len(detections)
            else:
                # Dry run - just count
                zipped_count += len(detections)
        
        return {
            "zipped": zipped_count,
            "skipped": skipped_count,
            "errors": error_count,
            "zip_files_created": zip_files_created,
            "dry_run": dry_run,
            "message": f"Zipped {zipped_count} images into {len(zip_files_created)} zip files"
        }
    
    def get_zip_status(self, db: Session) -> Dict[str, Any]:
        """Get status of auto-zip service"""
        config = self.get_config(db)
        
        # Count images that would be zipped
        if config["enabled"]:
            cutoff_date = datetime.utcnow() - timedelta(days=config["retention_months"] * 30)
            count = db.query(Detection).filter(
                Detection.timestamp < cutoff_date,
                Detection.image_path.isnot(None)
            ).count()
        else:
            count = 0
        
        # Get zip files info
        zip_root = Path(self.zip_root)
        zip_files = []
        total_zip_size = 0
        
        if zip_root.exists():
            for zip_file in zip_root.glob("*.zip"):
                size = zip_file.stat().st_size
                total_zip_size += size
                zip_files.append({
                    "filename": zip_file.name,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat()
                })
        
        return {
            "enabled": config["enabled"],
            "retention_months": config["retention_months"],
            "images_to_zip": count,
            "zip_files_count": len(zip_files),
            "total_zip_size_mb": round(total_zip_size / (1024 * 1024), 2),
            "zip_files": zip_files
        }


# Global instance
auto_zip_service = AutoZipService()

