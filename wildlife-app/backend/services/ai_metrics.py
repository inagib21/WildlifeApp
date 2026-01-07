"""Performance metrics tracking for AI backends"""
import time
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BackendMetrics:
    """Metrics for a single backend"""
    backend_name: str
    total_predictions: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0
    total_inference_time: float = 0.0
    min_inference_time: float = float('inf')
    max_inference_time: float = 0.0
    total_confidence: float = 0.0
    last_used: Optional[datetime] = None
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))  # Last 100 inference times
    recent_confidences: deque = field(default_factory=lambda: deque(maxlen=100))  # Last 100 confidences
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def avg_inference_time(self) -> float:
        """Average inference time in milliseconds"""
        if self.successful_predictions == 0:
            return 0.0
        return (self.total_inference_time / self.successful_predictions) * 1000
    
    @property
    def avg_confidence(self) -> float:
        """Average confidence score"""
        if self.successful_predictions == 0:
            return 0.0
        return self.total_confidence / self.successful_predictions
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage"""
        if self.total_predictions == 0:
            return 0.0
        return (self.successful_predictions / self.total_predictions) * 100.0
    
    @property
    def recent_avg_time(self) -> float:
        """Average of recent inference times (last 100)"""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times) * 1000
    
    @property
    def recent_avg_confidence(self) -> float:
        """Average of recent confidences (last 100)"""
        if not self.recent_confidences:
            return 0.0
        return sum(self.recent_confidences) / len(self.recent_confidences)


class AIMetricsTracker:
    """Track performance metrics for all AI backends"""
    
    def __init__(self):
        self.metrics: Dict[str, BackendMetrics] = {}
        self.lock = Lock()
        self.start_time = datetime.now()
    
    def record_prediction(
        self,
        backend_name: str,
        inference_time: float,
        success: bool,
        confidence: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Record a prediction result"""
        with self.lock:
            if backend_name not in self.metrics:
                self.metrics[backend_name] = BackendMetrics(backend_name=backend_name)
            
            metrics = self.metrics[backend_name]
            metrics.total_predictions += 1
            metrics.last_used = datetime.now()
            
            if success:
                metrics.successful_predictions += 1
                metrics.total_inference_time += inference_time
                metrics.min_inference_time = min(metrics.min_inference_time, inference_time)
                metrics.max_inference_time = max(metrics.max_inference_time, inference_time)
                metrics.recent_times.append(inference_time)
                
                if confidence is not None:
                    metrics.total_confidence += confidence
                    metrics.recent_confidences.append(confidence)
            else:
                metrics.failed_predictions += 1
                if error:
                    metrics.error_counts[error] += 1
    
    def get_metrics(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific backend or all backends"""
        with self.lock:
            if backend_name:
                if backend_name not in self.metrics:
                    return {}
                metrics = self.metrics[backend_name]
                return {
                    "backend_name": metrics.backend_name,
                    "total_predictions": metrics.total_predictions,
                    "successful_predictions": metrics.successful_predictions,
                    "failed_predictions": metrics.failed_predictions,
                    "success_rate": round(metrics.success_rate, 2),
                    "avg_inference_time_ms": round(metrics.avg_inference_time, 2),
                    "min_inference_time_ms": round(metrics.min_inference_time * 1000, 2) if metrics.min_inference_time != float('inf') else 0,
                    "max_inference_time_ms": round(metrics.max_inference_time * 1000, 2),
                    "recent_avg_time_ms": round(metrics.recent_avg_time, 2),
                    "avg_confidence": round(metrics.avg_confidence, 3),
                    "recent_avg_confidence": round(metrics.recent_avg_confidence, 3),
                    "last_used": metrics.last_used.isoformat() if metrics.last_used else None,
                    "error_counts": dict(metrics.error_counts),
                    "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
                }
            else:
                # Return all metrics
                return {
                    name: self.get_metrics(name)
                    for name in self.metrics.keys()
                }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics across all backends"""
        with self.lock:
            if not self.metrics:
                return {
                    "total_backends": 0,
                    "total_predictions": 0,
                    "total_successful": 0,
                    "total_failed": 0,
                    "overall_success_rate": 0.0,
                    "fastest_backend": None,
                    "most_accurate_backend": None,
                    "most_used_backend": None
                }
            
            total_predictions = sum(m.total_predictions for m in self.metrics.values())
            total_successful = sum(m.successful_predictions for m in self.metrics.values())
            total_failed = sum(m.failed_predictions for m in self.metrics.values())
            
            # Find fastest backend (by recent average)
            fastest = min(
                self.metrics.items(),
                key=lambda x: x[1].recent_avg_time if x[1].recent_avg_time > 0 else float('inf')
            )[0] if self.metrics else None
            
            # Find most accurate backend (by recent average confidence)
            most_accurate = max(
                self.metrics.items(),
                key=lambda x: x[1].recent_avg_confidence
            )[0] if self.metrics else None
            
            # Find most used backend
            most_used = max(
                self.metrics.items(),
                key=lambda x: x[1].total_predictions
            )[0] if self.metrics else None
            
            return {
                "total_backends": len(self.metrics),
                "total_predictions": total_predictions,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "overall_success_rate": round((total_successful / total_predictions * 100) if total_predictions > 0 else 0.0, 2),
                "fastest_backend": fastest,
                "most_accurate_backend": most_accurate,
                "most_used_backend": most_used,
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "backends": list(self.metrics.keys())
            }
    
    def reset_metrics(self, backend_name: Optional[str] = None):
        """Reset metrics for a specific backend or all backends"""
        with self.lock:
            if backend_name:
                if backend_name in self.metrics:
                    del self.metrics[backend_name]
            else:
                self.metrics.clear()
                self.start_time = datetime.now()


# Global metrics tracker instance
ai_metrics_tracker = AIMetricsTracker()

