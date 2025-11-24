"""Task status tracking service for monitoring long-running operations"""
import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """Information about a task"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key in ['created_at', 'started_at', 'completed_at']:
            if data[key]:
                data[key] = data[key].isoformat()
        # Convert enum to string
        data['status'] = data['status'].value
        return data


class TaskTracker:
    """Service for tracking task status and progress"""
    
    def __init__(self, max_tasks: int = 1000, cleanup_interval_seconds: int = 3600):
        """
        Initialize task tracker
        
        Args:
            max_tasks: Maximum number of tasks to keep in memory
            cleanup_interval_seconds: How often to cleanup old tasks (in seconds)
        """
        self.tasks: Dict[str, TaskInfo] = {}
        self.max_tasks = max_tasks
        self.cleanup_interval = cleanup_interval_seconds
        self.last_cleanup = time.time()
        self.lock = threading.Lock()
    
    def create_task(
        self,
        task_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new task and return its ID
        
        Args:
            task_type: Type of task (e.g., 'image_processing', 'backup', 'archival')
            metadata: Optional metadata about the task
        
        Returns:
            Task ID (UUID string)
        """
        task_id = str(uuid.uuid4())
        
        task = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        with self.lock:
            self._cleanup_if_needed()
            self.tasks[task_id] = task
        
        logger.info(f"Created task {task_id} of type {task_type}")
        return task_id
    
    def start_task(self, task_id: str, message: Optional[str] = None) -> bool:
        """
        Mark a task as started
        
        Args:
            task_id: Task ID
            message: Optional status message
        
        Returns:
            True if task was found and started, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status != TaskStatus.PENDING:
                logger.warning(f"Task {task_id} cannot be started (current status: {task.status})")
                return False
            
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            if message:
                task.message = message
        
        logger.info(f"Started task {task_id}")
        return True
    
    def update_task(
        self,
        task_id: str,
        progress: Optional[float] = None,
        message: Optional[str] = None
    ) -> bool:
        """
        Update task progress
        
        Args:
            task_id: Task ID
            progress: Progress (0.0 to 1.0)
            message: Optional status message
        
        Returns:
            True if task was found and updated, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status != TaskStatus.RUNNING:
                logger.warning(f"Task {task_id} cannot be updated (current status: {task.status})")
                return False
            
            if progress is not None:
                task.progress = max(0.0, min(1.0, progress))  # Clamp to 0.0-1.0
            if message:
                task.message = message
        
        return True
    
    def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None
    ) -> bool:
        """
        Mark a task as completed
        
        Args:
            task_id: Task ID
            result: Optional result data
            message: Optional completion message
        
        Returns:
            True if task was found and completed, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.progress = 1.0
            if result:
                task.result = result
            if message:
                task.message = message
        
        logger.info(f"Completed task {task_id}")
        return True
    
    def fail_task(
        self,
        task_id: str,
        error: str,
        message: Optional[str] = None
    ) -> bool:
        """
        Mark a task as failed
        
        Args:
            task_id: Task ID
            error: Error message
            message: Optional status message
        
        Returns:
            True if task was found and failed, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error = error
            if message:
                task.message = message
        
        logger.error(f"Task {task_id} failed: {error}")
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
        
        Returns:
            True if task was found and cancelled, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            task.message = "Task cancelled by user"
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        Get task information
        
        Args:
            task_id: Task ID
        
        Returns:
            TaskInfo if found, None otherwise
        """
        with self.lock:
            return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        task_type: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TaskInfo]:
        """
        List tasks with optional filtering
        
        Args:
            task_type: Filter by task type
            status: Filter by status
            limit: Maximum number of tasks to return
            offset: Number of tasks to skip
        
        Returns:
            List of TaskInfo objects
        """
        with self.lock:
            tasks = list(self.tasks.values())
            
            # Apply filters
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            if status:
                tasks = [t for t in tasks if t.status == status]
            
            # Sort by created_at descending (newest first)
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            
            # Apply pagination
            return tasks[offset:offset + limit]
    
    def get_task_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tasks
        
        Returns:
            Dictionary with task statistics
        """
        with self.lock:
            stats = {
                "total": len(self.tasks),
                "by_status": defaultdict(int),
                "by_type": defaultdict(int),
                "running": 0,
                "completed": 0,
                "failed": 0
            }
            
            for task in self.tasks.values():
                stats["by_status"][task.status.value] += 1
                stats["by_type"][task.task_type] += 1
                
                if task.status == TaskStatus.RUNNING:
                    stats["running"] += 1
                elif task.status == TaskStatus.COMPLETED:
                    stats["completed"] += 1
                elif task.status == TaskStatus.FAILED:
                    stats["failed"] += 1
            
            return dict(stats)
    
    def _cleanup_if_needed(self):
        """Clean up old completed/failed tasks if needed"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        self.last_cleanup = current_time
        
        # Keep only recent tasks or running tasks
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Keep tasks from last 7 days
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            # Keep running/pending tasks
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                continue
            
            # Remove old completed/failed/cancelled tasks
            if task.completed_at and task.completed_at < cutoff_time:
                tasks_to_remove.append(task_id)
        
        # If we still have too many tasks, remove oldest completed ones
        if len(self.tasks) - len(tasks_to_remove) > self.max_tasks:
            remaining = [t for t in self.tasks.values() if t.task_id not in tasks_to_remove]
            remaining.sort(key=lambda t: t.created_at)
            
            # Remove oldest until we're under limit
            while len(remaining) + len(tasks_to_remove) > self.max_tasks:
                if remaining:
                    tasks_to_remove.append(remaining.pop(0).task_id)
                else:
                    break
        
        # Remove tasks
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")


# Global instance
task_tracker = TaskTracker()

