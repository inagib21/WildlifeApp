# Router Error Handling Enhancements

This document tracks the enhancement of error handling across all routers.

## Completed Enhancements

### ✅ Main Application (`main.py`)
- Global exception handler
- Request/Response logging middleware
- Enhanced logging format

### ✅ Detections Router (`routers/detections.py`)
- ErrorContext usage
- Database error handling
- Enhanced error logging

### ✅ Media Router (`routers/media.py`)
- Multiple path resolution strategies
- Detailed error logging
- Better error messages

### ✅ Webhooks Router (`routers/webhooks.py`)
- Comprehensive error categorization
- Detailed audit logging
- Enhanced error messages

## Enhancement Pattern

All routers should follow this pattern:

```python
from utils.error_handler import ErrorContext, handle_database_error, log_error
from sqlalchemy.exc import SQLAlchemyError

@router.get("/endpoint")
def my_endpoint(request: Request, db: Session = Depends(get_db)):
    with ErrorContext("my_endpoint"):
        try:
            # Endpoint logic
            pass
        except SQLAlchemyError as db_error:
            raise handle_database_error(db_error, "my_endpoint")
        except HTTPException:
            raise
        except Exception as e:
            log_error(e, "my_endpoint", {
                "endpoint": str(request.url.path),
                "method": request.method
            })
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
```

## Status

- ✅ Main application
- ✅ Detections router
- ✅ Media router  
- ✅ Webhooks router
- ⏳ Cameras router (in progress)
- ⏳ System router
- ⏳ Analytics router
- ⏳ Notifications router
- ⏳ Backups router
- ⏳ Config router
- ⏳ Auth router
- ⏳ Audit router
- ⏳ Events router
- ⏳ Debug router

