"""Background task scheduler for automated operations"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Callable
import threading

# Try to import APScheduler, but handle gracefully if not available
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None
    IntervalTrigger = None

logger = logging.getLogger(__name__)

if not APSCHEDULER_AVAILABLE:
    logger.warning("APScheduler not available. Scheduled tasks will be disabled. Install with: pip install APScheduler>=3.10.0")

try:
    from ..services.backup import backup_service
    from ..services.notifications import notification_service
except ImportError:
    from services.backup import backup_service
    from services.notifications import notification_service


class TaskScheduler:
    """Scheduler for automated background tasks"""
    
    def __init__(self):
        if not APSCHEDULER_AVAILABLE:
            self.scheduler = None
            logger.warning("Task scheduler not available (APScheduler not installed)")
            return
        
        try:
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            logger.info("Task scheduler started")
        except Exception as e:
            logger.error(f"Failed to start task scheduler: {e}")
            self.scheduler = None
    
    def _check_scheduler(self):
        """Check if scheduler is available"""
        if not APSCHEDULER_AVAILABLE or self.scheduler is None:
            logger.warning("Scheduler not available - cannot schedule task")
            return False
        return True
    
    def schedule_daily_backup(self, hour: int = 2, minute: int = 0):
        """
        Schedule daily database backups
        
        Args:
            hour: Hour of day (0-23) to run backup
            minute: Minute of hour (0-59) to run backup
        """
        def backup_job():
            try:
                logger.info(f"Starting scheduled daily backup at {datetime.now()}")
                backup_path = backup_service.create_backup()
                if backup_path:
                    logger.info(f"Scheduled backup completed: {backup_path}")
                    # Clean up old backups (keep last 30)
                    deleted = backup_service.cleanup_old_backups(keep_count=30)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old backup(s)")
                else:
                    logger.error("Scheduled backup failed")
            except Exception as e:
                logger.error(f"Scheduled backup error: {e}", exc_info=True)
        
        if not self._check_scheduler():
            return
        
        # Schedule daily at specified time
        self.scheduler.add_job(
            backup_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_backup',
            name='Daily Database Backup',
            replace_existing=True
        )
        logger.info(f"Scheduled daily backup at {hour:02d}:{minute:02d}")
    
    def schedule_weekly_backup(self, day_of_week: int = 0, hour: int = 3, minute: int = 0):
        """
        Schedule weekly database backups
        
        Args:
            day_of_week: Day of week (0=Monday, 6=Sunday)
            hour: Hour of day (0-23)
            minute: Minute of hour (0-59)
        """
        def backup_job():
            try:
                logger.info(f"Starting scheduled weekly backup at {datetime.now()}")
                backup_path = backup_service.create_backup()
                if backup_path:
                    logger.info(f"Scheduled weekly backup completed: {backup_path}")
            except Exception as e:
                logger.error(f"Scheduled weekly backup error: {e}", exc_info=True)
        
        if not self._check_scheduler():
            return
        
        # Schedule weekly
        self.scheduler.add_job(
            backup_job,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id='weekly_backup',
            name='Weekly Database Backup',
            replace_existing=True
        )
        logger.info(f"Scheduled weekly backup on day {day_of_week} at {hour:02d}:{minute:02d}")
    
    def schedule_monthly_backup(self, day: int = 1, hour: int = 2, minute: int = 0):
        """
        Schedule monthly database backups
        
        Args:
            day: Day of month (1-31) to run backup
            hour: Hour of day (0-23) to run backup
            minute: Minute of hour (0-59) to run backup
        """
        def backup_job():
            try:
                logger.info(f"Starting scheduled monthly backup at {datetime.now()}")
                backup_path = backup_service.create_backup()
                if backup_path:
                    logger.info(f"Scheduled monthly backup completed: {backup_path}")
                    # Clean up old backups (keep last 30)
                    deleted = backup_service.cleanup_old_backups(keep_count=30)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old backup(s)")
                else:
                    logger.error("Scheduled monthly backup failed")
            except Exception as e:
                logger.error(f"Scheduled monthly backup error: {e}", exc_info=True)
        
        if not self._check_scheduler():
            return
        
        # Schedule monthly on specified day
        self.scheduler.add_job(
            backup_job,
            trigger=CronTrigger(day=day, hour=hour, minute=minute),
            id='monthly_backup',
            name='Monthly Database Backup',
            replace_existing=True
        )
        logger.info(f"Scheduled monthly backup on day {day} at {hour:02d}:{minute:02d}")
    
    def schedule_cleanup(self, interval_hours: int = 24):
        """
        Schedule periodic cleanup of old backups
        
        Args:
            interval_hours: Hours between cleanup runs
        """
        def cleanup_job():
            try:
                logger.info(f"Starting scheduled backup cleanup at {datetime.now()}")
                deleted = backup_service.cleanup_old_backups(keep_count=30)
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old backup(s)")
            except Exception as e:
                logger.error(f"Scheduled cleanup error: {e}", exc_info=True)
        
        if not self._check_scheduler():
            return
        
        self.scheduler.add_job(
            cleanup_job,
            trigger=IntervalTrigger(hours=interval_hours),
            id='backup_cleanup',
            name='Backup Cleanup',
            replace_existing=True
        )
        logger.info(f"Scheduled backup cleanup every {interval_hours} hours")
    
    def schedule_custom_job(
        self,
        func: Callable,
        job_id: str,
        name: str,
        trigger_type: str = "interval",
        **trigger_kwargs
    ):
        """
        Schedule a custom job
        
        Args:
            func: Function to execute
            job_id: Unique job identifier
            name: Human-readable job name
            trigger_type: 'interval', 'cron', or 'date'
            **trigger_kwargs: Trigger-specific parameters
        """
        if trigger_type == "interval":
            trigger = IntervalTrigger(**trigger_kwargs)
        elif trigger_type == "cron":
            trigger = CronTrigger(**trigger_kwargs)
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")
        
        if not self._check_scheduler():
            return
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=name,
            replace_existing=True
        )
        logger.info(f"Scheduled custom job '{name}' (ID: {job_id})")
    
    def get_jobs(self):
        """Get list of all scheduled jobs"""
        if not self._check_scheduler():
            return []
        
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        if not self._check_scheduler():
            return False
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if not self._check_scheduler():
            return
        
        try:
            self.scheduler.shutdown()
            logger.info("Task scheduler shut down")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")


# Global scheduler instance
task_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get or create the global scheduler instance"""
    global task_scheduler
    if task_scheduler is None:
        task_scheduler = TaskScheduler()
    return task_scheduler


def schedule_audit_log_cleanup(retention_days: int = 90, day: int = 1, hour: int = 3, minute: int = 0):
    """
    Schedule automatic cleanup of old audit logs (monthly)
    
    Args:
        retention_days: Number of days to keep logs
        day: Day of month (1-31) to run cleanup
        hour: Hour of day to run cleanup
        minute: Minute of hour to run cleanup
    """
    def cleanup_job():
        try:
            from database import SessionLocal, AuditLog
            from datetime import datetime, timedelta
            
            logger.info(f"Starting scheduled audit log cleanup (retention: {retention_days} days)")
            db = SessionLocal()
            try:
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                deleted_count = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
                db.commit()
                logger.info(f"Scheduled audit log cleanup completed: {deleted_count} log(s) deleted")
            except Exception as e:
                db.rollback()
                logger.error(f"Scheduled audit log cleanup error: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to run scheduled audit log cleanup: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    scheduler.scheduler.add_job(
        cleanup_job,
        trigger=CronTrigger(day=day, hour=hour, minute=minute),
        id='audit_log_cleanup',
        name='Audit Log Cleanup',
        replace_existing=True
    )
    logger.info(f"Scheduled audit log cleanup monthly on day {day} at {hour:02d}:{minute:02d} (retention: {retention_days} days)")


def initialize_scheduled_tasks():
    """Initialize default scheduled tasks"""
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot initialize scheduled tasks - APScheduler not installed")
        return
    
    scheduler = get_scheduler()
    
    if scheduler.scheduler is None:
        logger.warning("Cannot initialize scheduled tasks - scheduler not started")
        return
    
    # Schedule monthly backup (configurable via environment variables)
    try:
        from config import BACKUP_SCHEDULE_MONTHLY_DAY, BACKUP_SCHEDULE_MONTHLY_HOUR
        schedule_monthly_backup(day=BACKUP_SCHEDULE_MONTHLY_DAY, hour=BACKUP_SCHEDULE_MONTHLY_HOUR, minute=0)
    except ImportError:
        # Default to 1st of month at 2 AM if config not available
        schedule_monthly_backup(day=1, hour=2, minute=0)
    
    # Schedule backup cleanup every 24 hours
    scheduler.schedule_cleanup(interval_hours=24)
    
    # Schedule audit log cleanup monthly on the 1st at 3:30 AM (90 day retention)
    schedule_audit_log_cleanup(retention_days=90, day=1, hour=3, minute=30)
    
    # Schedule image archival daily at 4:00 AM (if enabled)
    try:
        from config import ARCHIVAL_ENABLED
        if ARCHIVAL_ENABLED:
            schedule_image_archival(hour=4, minute=0)
    except ImportError:
        pass  # Archival not configured
    
    # Schedule camera sync every 6 hours
    schedule_camera_sync(interval_hours=6)
    
    # Schedule system health checks every hour
    schedule_system_health_check(interval_hours=1)
    
    # Schedule weekly report generation on Monday at 8:00 AM
    schedule_report_generation(day_of_week=0, hour=8, minute=0)
    
    # Schedule auto-zip task (daily at 5:00 AM, checks if enabled in settings)
    schedule_auto_zip(hour=5, minute=0)
    
    logger.info("Initialized default scheduled tasks")


def schedule_monthly_backup(day: int = 1, hour: int = 2, minute: int = 0):
    """
    Schedule monthly database backups
    
    Args:
        day: Day of month (1-31) to run backup
        hour: Hour of day (0-23) to run backup
        minute: Minute of hour (0-59) to run backup
    """
    scheduler = get_scheduler()
    scheduler.schedule_monthly_backup(day=day, hour=hour, minute=minute)


def schedule_image_archival(hour: int = 4, minute: int = 0, limit: int = 100):
    """
    Schedule automatic image archival
    
    Args:
        hour: Hour of day to run archival
        minute: Minute of hour to run archival
        limit: Maximum number of detections to process per run
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot schedule image archival - APScheduler not installed")
        return
    
    def archival_job():
        try:
            from database import SessionLocal
            from services.archival import archival_service
            
            logger.info(f"Starting scheduled image archival (limit: {limit})")
            db = SessionLocal()
            try:
                stats = archival_service.archive_detections(db, limit=limit)
                logger.info(f"Scheduled image archival completed: {stats}")
            except Exception as e:
                logger.error(f"Scheduled image archival error: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to run scheduled image archival: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    if scheduler.scheduler is None:
        logger.warning("Cannot schedule image archival - scheduler not started")
        return
    
    scheduler.scheduler.add_job(
        archival_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id='image_archival',
        name='Image Archival',
        replace_existing=True
    )
    logger.info(f"Scheduled image archival daily at {hour:02d}:{minute:02d} (limit: {limit})")


def schedule_auto_zip(hour: int = 5, minute: int = 0):
    """
    Schedule automatic image zipping based on retention period
    
    Args:
        hour: Hour of day to run auto-zip check
        minute: Minute of hour to run auto-zip check
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot schedule auto-zip - APScheduler not installed")
        return
    
    def auto_zip_job():
        try:
            from database import SessionLocal
            from services.auto_zip import auto_zip_service
            
            logger.info("Starting scheduled auto-zip check")
            db = SessionLocal()
            try:
                config = auto_zip_service.get_config(db)
                
                if not config["enabled"]:
                    logger.debug("Auto-zip is disabled, skipping")
                    return
                
                retention_months = config["retention_months"]
                stats = auto_zip_service.zip_images(
                    db=db,
                    retention_months=retention_months,
                    dry_run=False
                )
                logger.info(f"Scheduled auto-zip completed: {stats}")
            except Exception as e:
                logger.error(f"Scheduled auto-zip error: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to run scheduled auto-zip: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    if scheduler.scheduler is None:
        logger.warning("Cannot schedule auto-zip - scheduler not started")
        return
    
    scheduler.scheduler.add_job(
        auto_zip_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id='auto_zip',
        name='Auto-Zip Old Images',
        replace_existing=True
    )
    logger.info(f"Scheduled auto-zip daily at {hour:02d}:{minute:02d}")


def schedule_camera_sync(interval_hours: int = 6):
    """
    Schedule periodic camera synchronization with MotionEye
    
    Args:
        interval_hours: Hours between sync runs
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot schedule camera sync - APScheduler not installed")
        return
    
    def sync_job():
        try:
            from camera_sync import sync_motioneye_cameras
            from database import SessionLocal, Camera
            from services.motioneye import MotionEyeClient
            from config import MOTIONEYE_URL, MOTIONEYE_USERNAME, MOTIONEYE_PASSWORD
            
            logger.info(f"Starting scheduled camera sync at {datetime.now()}")
            db = SessionLocal()
            try:
                motioneye_client = MotionEyeClient(
                    base_url=MOTIONEYE_URL,
                    username=MOTIONEYE_USERNAME,
                    password=MOTIONEYE_PASSWORD
                )
                sync_motioneye_cameras(db, motioneye_client, Camera)
                logger.info("Scheduled camera sync completed")
            except Exception as e:
                logger.error(f"Scheduled camera sync error: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to run scheduled camera sync: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    if scheduler.scheduler is None:
        logger.warning("Cannot schedule camera sync - scheduler not started")
        return
    
    scheduler.scheduler.add_job(
        sync_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id='camera_sync',
        name='Camera Sync',
        replace_existing=True
    )
    logger.info(f"Scheduled camera sync every {interval_hours} hours")


def schedule_system_health_check(interval_hours: int = 1):
    """
    Schedule periodic system health checks
    
    Args:
        interval_hours: Hours between health checks
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot schedule system health check - APScheduler not installed")
        return
    
    def health_check_job():
        try:
            import psutil
            import os
            from database import SessionLocal
            from services.notifications import notification_service
            
            logger.info(f"Starting scheduled system health check at {datetime.now()}")
            
            # Check disk space (use current directory root on Windows)
            try:
                root_path = 'C:\\' if os.name == 'nt' else '/'
                disk = psutil.disk_usage(root_path)
            except Exception:
                # Fallback to current directory
                disk = psutil.disk_usage('.')
            disk_percent = (disk.used / disk.total) * 100
            
            if disk_percent > 90:
                notification_service.send_system_alert(
                    subject="High Disk Usage",
                    message=f"Disk usage is at {disk_percent:.1f}%. Consider cleaning up old files.",
                    alert_type="warning"
                )
            
            # Check memory
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                notification_service.send_system_alert(
                    subject="High Memory Usage",
                    message=f"Memory usage is at {memory.percent:.1f}%.",
                    alert_type="warning"
                )
            
            logger.info("Scheduled system health check completed")
        except Exception as e:
            logger.error(f"Scheduled system health check error: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    if scheduler.scheduler is None:
        logger.warning("Cannot schedule system health check - scheduler not started")
        return
    
    scheduler.scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id='system_health_check',
        name='System Health Check',
        replace_existing=True
    )
    logger.info(f"Scheduled system health check every {interval_hours} hours")


def schedule_report_generation(day_of_week: int = 0, hour: int = 8, minute: int = 0):
    """
    Schedule weekly report generation
    
    Args:
        day_of_week: Day of week (0=Monday, 6=Sunday)
        hour: Hour of day (0-23)
        minute: Minute of hour (0-59)
    """
    if not APSCHEDULER_AVAILABLE:
        logger.warning("Cannot schedule report generation - APScheduler not installed")
        return
    
    def report_job():
        try:
            from database import SessionLocal, Detection
            from datetime import datetime, timedelta
            import os
            
            logger.info(f"Starting scheduled report generation at {datetime.now()}")
            db = SessionLocal()
            try:
                # Generate weekly summary
                week_ago = datetime.now() - timedelta(days=7)
                detections = db.query(Detection).filter(Detection.timestamp >= week_ago).all()
                
                # Create reports directory if it doesn't exist
                reports_dir = "./reports"
                os.makedirs(reports_dir, exist_ok=True)
                
                # Generate summary (could be extended to create PDF/CSV)
                summary = {
                    "period": f"{week_ago.date()} to {datetime.now().date()}",
                    "total_detections": len(detections),
                    "unique_species": len(set(d.species for d in detections if d.species)),
                    "generated_at": datetime.now().isoformat()
                }
                
                logger.info(f"Scheduled report generation completed: {summary}")
            except Exception as e:
                logger.error(f"Scheduled report generation error: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to run scheduled report generation: {e}", exc_info=True)
    
    scheduler = get_scheduler()
    if scheduler.scheduler is None:
        logger.warning("Cannot schedule report generation - scheduler not started")
        return
    
    scheduler.scheduler.add_job(
        report_job,
        trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
        id='report_generation',
        name='Weekly Report Generation',
        replace_existing=True
    )
    logger.info(f"Scheduled weekly report generation on day {day_of_week} at {hour:02d}:{minute:02d}")
