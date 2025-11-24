"""Background task scheduler for automated operations"""
import asyncio
import logging
from datetime import datetime, time
from typing import Optional, Callable
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timedelta

try:
    from ..services.backup import backup_service
    from ..services.notifications import notification_service
except ImportError:
    from services.backup import backup_service
    from services.notifications import notification_service

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Scheduler for automated background tasks"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Task scheduler started")
    
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
        
        # Schedule weekly
        self.scheduler.add_job(
            backup_job,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id='weekly_backup',
            name='Weekly Database Backup',
            replace_existing=True
        )
        logger.info(f"Scheduled weekly backup on day {day_of_week} at {hour:02d}:{minute:02d}")
    
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
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Task scheduler shut down")


# Global scheduler instance
task_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get or create the global scheduler instance"""
    global task_scheduler
    if task_scheduler is None:
        task_scheduler = TaskScheduler()
    return task_scheduler


def schedule_audit_log_cleanup(retention_days: int = 90, hour: int = 3, minute: int = 0):
    """
    Schedule automatic cleanup of old audit logs
    
    Args:
        retention_days: Number of days to keep logs
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
        trigger=CronTrigger(hour=hour, minute=minute),
        id='audit_log_cleanup',
        name='Audit Log Cleanup',
        replace_existing=True
    )
    logger.info(f"Scheduled audit log cleanup daily at {hour:02d}:{minute:02d} (retention: {retention_days} days)")


def initialize_scheduled_tasks():
    """Initialize default scheduled tasks"""
    scheduler = get_scheduler()
    
    # Schedule daily backup at 2 AM
    scheduler.schedule_daily_backup(hour=2, minute=0)
    
    # Schedule weekly backup on Sunday at 3 AM
    scheduler.schedule_weekly_backup(day_of_week=6, hour=3, minute=0)
    
    # Schedule backup cleanup every 24 hours
    scheduler.schedule_cleanup(interval_hours=24)
    
    # Schedule audit log cleanup daily at 3:30 AM (90 day retention)
    schedule_audit_log_cleanup(retention_days=90, hour=3, minute=30)
    
    logger.info("Initialized default scheduled tasks")

