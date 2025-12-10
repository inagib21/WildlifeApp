"""Centralized error handling and debugging utilities"""
import logging
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import sys

logger = logging.getLogger(__name__)


class ErrorContext:
    """Context manager for error tracking"""
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        logger.debug(f"Starting {self.operation}", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is None:
            logger.debug(f"Completed {self.operation} in {duration:.3f}s", extra=self.context)
        else:
            error_msg = str(exc_val) if exc_val else str(exc_type)
            logger.error(
                f"Failed {self.operation} after {duration:.3f}s: {error_msg}",
                extra={**self.context, "error_type": exc_type.__name__, "error": error_msg},
                exc_info=True
            )
        return False  # Don't suppress exceptions


def log_error(
    error: Exception,
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR
) -> None:
    """
    Log an error with full context
    
    Args:
        error: The exception that occurred
        operation: Description of what was being done
        context: Additional context information
        level: Logging level (default: ERROR)
    """
    error_type = type(error).__name__
    error_msg = str(error)
    error_traceback = traceback.format_exc()
    
    log_data = {
        "operation": operation,
        "error_type": error_type,
        "error_message": error_msg,
        "context": context or {},
    }
    
    if level >= logging.ERROR:
        logger.error(
            f"❌ Error in {operation}: {error_type}: {error_msg}",
            extra=log_data,
            exc_info=True
        )
    else:
        logger.warning(
            f"⚠️ Warning in {operation}: {error_type}: {error_msg}",
            extra=log_data
        )


def create_error_response(
    error: Exception,
    request: Request,
    operation: str,
    status_code: int = 500,
    include_traceback: bool = False
) -> JSONResponse:
    """
    Create a standardized error response
    
    Args:
        error: The exception that occurred
        request: FastAPI request object
        operation: Description of what was being done
        status_code: HTTP status code
        include_traceback: Whether to include traceback in response (debug only)
    
    Returns:
        JSONResponse with error details
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Log the error
    log_error(error, operation, {
        "endpoint": str(request.url.path),
        "method": request.method,
        "status_code": status_code
    })
    
    # Build error response
    error_response = {
        "status": "error",
        "error_type": error_type,
        "error_message": error_msg,
        "operation": operation,
        "endpoint": str(request.url.path),
        "timestamp": logging.Formatter().formatTime(logging.LogRecord(
            name="", level=0, pathname="", lineno=0,
            msg="", args=(), exc_info=None
        ))
    }
    
    # Include traceback in debug mode
    if include_traceback or logger.isEnabledFor(logging.DEBUG):
        error_response["traceback"] = traceback.format_exc()
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


def handle_database_error(error: SQLAlchemyError, operation: str) -> HTTPException:
    """
    Handle database errors with appropriate logging and user-friendly messages
    
    Args:
        error: SQLAlchemy exception
        operation: Description of the database operation
    
    Returns:
        HTTPException with appropriate status code and message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Categorize database errors
    if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        status_code = 503  # Service Unavailable
        user_message = "Database connection error. Please try again later."
    elif "constraint" in error_msg.lower() or "unique" in error_msg.lower():
        status_code = 409  # Conflict
        user_message = "Data conflict. The record may already exist."
    elif "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
        status_code = 404  # Not Found
        user_message = "Requested resource not found."
    else:
        status_code = 500  # Internal Server Error
        user_message = "Database error occurred."
    
    log_error(error, operation, {
        "error_type": error_type,
        "status_code": status_code
    })
    
    return HTTPException(
        status_code=status_code,
        detail={
            "status": "error",
            "error_type": error_type,
            "message": user_message,
            "operation": operation
        }
    )


def log_request(request: Request, response_time: Optional[float] = None) -> None:
    """
    Log HTTP request details
    
    Args:
        request: FastAPI request object
        response_time: Optional response time in seconds
    """
    log_data = {
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    
    if response_time:
        log_data["response_time_ms"] = response_time * 1000
    
    logger.info(
        f"{request.method} {request.url.path}",
        extra=log_data
    )


def log_response(
    request: Request,
    status_code: int,
    response_time: Optional[float] = None,
    error: Optional[Exception] = None
) -> None:
    """
    Log HTTP response details
    
    Args:
        request: FastAPI request object
        status_code: HTTP status code
        response_time: Optional response time in seconds
        error: Optional error that occurred
    """
    log_data = {
        "method": request.method,
        "path": str(request.url.path),
        "status_code": status_code,
        "client_ip": request.client.host if request.client else None,
    }
    
    if response_time:
        log_data["response_time_ms"] = response_time * 1000
    
    if error:
        log_data["error"] = str(error)
        log_data["error_type"] = type(error).__name__
    
    if status_code >= 500:
        logger.error(f"{request.method} {request.url.path} -> {status_code}", extra=log_data)
    elif status_code >= 400:
        logger.warning(f"{request.method} {request.url.path} -> {status_code}", extra=log_data)
    else:
        logger.info(f"{request.method} {request.url.path} -> {status_code}", extra=log_data)


def safe_execute(
    func,
    operation: str,
    default_return: Any = None,
    raise_on_error: bool = True,
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling
    
    Args:
        func: Function to execute
        operation: Description of the operation
        default_return: Value to return on error if raise_on_error is False
        raise_on_error: Whether to raise exception or return default
        **kwargs: Arguments to pass to function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(**kwargs)
    except Exception as e:
        log_error(e, operation)
        if raise_on_error:
            raise
        return default_return

