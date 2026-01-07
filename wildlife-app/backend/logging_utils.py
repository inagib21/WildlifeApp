import logging
import os
import sys
import json
from datetime import datetime
from typing import Iterable, Any, Dict, Optional

class JSONFormatter(logging.Formatter):
    """JSON log formatter"""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno
        }
        
        # Add trace info if available
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields but exclude standard ones
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in ["args", "asciitime", "created", "exc_info", "exc_text", "filename",
                              "funcName", "levelname", "levelno", "lineno", "module",
                              "msecs", "message", "msg", "name", "pathname", "process",
                              "processName", "relativeCreated", "stack_info", "thread", "threadName"]:
                    log_obj[key] = value
                    
        return json.dumps(log_obj)

def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}

def configure_logging(level: int = logging.INFO, json_format: bool = False):
    """Configure root logger"""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    log_file = os.getenv("LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to setup file logging: {e}")

def configure_access_logs(env_names: Iterable[str] = ("DISABLE_UVICORN_ACCESS_LOGS",)) -> bool:
    disable = any(
        _truthy(os.getenv(name, "0"))
        for name in env_names
    )
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.disabled = disable
    return disable
