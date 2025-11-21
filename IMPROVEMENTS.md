# Wildlife App - Security, Performance & Code Quality Improvements

## 🔴 CRITICAL SECURITY ISSUES (Fix Immediately)

### 1. Hardcoded Credentials
**Location:** `wildlife-app/backend/main.py` lines 1194, 1314

**Problem:** Camera credentials are hardcoded in source code
```python
auth = ("root", "ismart12")  # ❌ SECURITY RISK
```

**Fix:** Move to environment variables
```python
# In .env file
THINGINO_CAMERA_USERNAME=root
THINGINO_CAMERA_PASSWORD=ismart12

# In main.py
THINGINO_USERNAME = os.getenv("THINGINO_CAMERA_USERNAME")
THINGINO_PASSWORD = os.getenv("THINGINO_CAMERA_PASSWORD")
auth = (THINGINO_USERNAME, THINGINO_PASSWORD) if THINGINO_USERNAME and THINGINO_PASSWORD else None
```

### 2. Hardcoded Database Credentials
**Location:** `wildlife-app/backend/main.py` line 222

**Problem:** Database password in source code
```python
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/wildlife"  # ❌
```

**Fix:** Use environment variables
```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'wildlife')}"
)
```

### 3. Overly Permissive CORS
**Location:** `wildlife-app/backend/main.py` lines 62-68, `speciesnet_server.py` line 24

**Problem:** Allows all methods and headers, speciesnet allows all origins
```python
allow_methods=["*"],  # ❌ Too permissive
allow_headers=["*"],  # ❌ Too permissive
allow_origins=["*"]   # ❌ In speciesnet_server.py
```

**Fix:** Restrict to specific origins and methods
```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods
    allow_headers=["Content-Type", "Authorization"],  # Specific headers
)

# In speciesnet_server.py - restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],  # Only backend
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
```

### 4. No Authentication/Authorization
**Problem:** All API endpoints are publicly accessible

**Fix:** Add API key authentication
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        return None  # No auth required if no key set
    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# Use on sensitive endpoints
@app.post("/cameras")
def add_camera(camera: CameraCreate, db: Session = Depends(get_db), api_key: str = Security(verify_api_key)):
    # ... existing code
```

## ⚡ PERFORMANCE IMPROVEMENTS

### 1. Database Connection Pooling
**Location:** `wildlife-app/backend/main.py` line 226

**Problem:** No connection pool configuration

**Fix:** Configure connection pooling
```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Number of connections to maintain
    max_overflow=20,        # Additional connections when pool is exhausted
    pool_pre_ping=True,     # Verify connections before using
    pool_recycle=3600,      # Recycle connections after 1 hour
    echo=False
)
```

### 2. Async Database Operations
**Problem:** Using synchronous SQLAlchemy blocks the event loop

**Fix:** Use async SQLAlchemy with asyncpg
```python
# Update requirements.txt
# asyncpg>=0.29.0  # Uncomment this

# In main.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL_ASYNC = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(
    DATABASE_URL_ASYNC,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Update endpoints to async
@app.get("/cameras", response_model=List[CameraResponse])
async def get_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()
    # ... rest of code
```

### 3. Add Caching for Frequently Accessed Data
**Problem:** System health and camera list are queried frequently

**Fix:** Add Redis or in-memory caching
```python
from functools import lru_cache
from datetime import timedelta
import time

# Simple in-memory cache
_cache = {}
_cache_ttl = {}

def get_cached(key: str, ttl: int = 60):
    """Get cached value if not expired"""
    if key in _cache:
        if time.time() - _cache_ttl.get(key, 0) < ttl:
            return _cache[key]
        else:
            del _cache[key]
            del _cache_ttl[key]
    return None

def set_cached(key: str, value: Any, ttl: int = 60):
    """Set cached value with TTL"""
    _cache[key] = value
    _cache_ttl[key] = time.time()

# Use in endpoints
@app.get("/system")
async def get_system_health():
    cached = get_cached("system_health", ttl=5)  # Cache for 5 seconds
    if cached:
        return cached
    
    result = await _compute_system_health()
    set_cached("system_health", result, ttl=5)
    return result
```

### 4. Add Rate Limiting
**Problem:** No protection against API abuse

**Fix:** Add rate limiting middleware
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@app.post("/process-image")
@limiter.limit("10/minute")  # 10 requests per minute
async def process_image_with_speciesnet(...):
    # ... existing code
```

### 5. Optimize Database Queries
**Problem:** Some queries could be more efficient

**Fix:** Add database indexes and optimize queries
```python
# Add indexes to models
class Detection(Base):
    # ... existing fields
    __table_args__ = (
        Index('idx_detection_timestamp', 'timestamp'),
        Index('idx_detection_camera_id', 'camera_id'),
        Index('idx_detection_species', 'species'),
        Index('idx_detection_file_hash', 'file_hash'),  # For deduplication
    )

# Use select_related for joins
from sqlalchemy.orm import selectinload

detections = await db.execute(
    select(Detection)
    .options(selectinload(Detection.camera))  # Eager load camera
    .order_by(Detection.timestamp.desc())
    .limit(50)
)
```

## 🏗️ CODE QUALITY IMPROVEMENTS

### 1. Split Large main.py File
**Problem:** 2606 lines in one file is hard to maintain

**Fix:** Split into modules
```
wildlife-app/backend/
├── main.py                 # FastAPI app setup, routes
├── config.py               # Configuration and environment variables
├── database.py             # Database setup and models
├── auth.py                 # Authentication/authorization
├── routers/
│   ├── cameras.py          # Camera endpoints
│   ├── detections.py       # Detection endpoints
│   ├── system.py           # System health endpoints
│   └── webhooks.py         # Webhook endpoints
├── services/
│   ├── speciesnet.py       # SpeciesNet integration
│   ├── motioneye.py        # MotionEye client
│   └── photo_scanner.py     # Photo scanning service
└── utils/
    ├── caching.py          # Caching utilities
    └── validators.py       # Input validation
```

### 2. Add Input Validation
**Problem:** Limited input validation on API endpoints

**Fix:** Add Pydantic validators
```python
from pydantic import BaseModel, validator, Field

class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., regex=r'^rtsp://|^http://')
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('url')
    def validate_url(cls, v):
        # Additional URL validation
        if '..' in v or '//' in v.replace('://', ''):
            raise ValueError('Invalid URL format')
        return v
```

### 3. Improve Error Handling
**Problem:** Generic exception handling in some places

**Fix:** Specific exception types and better error messages
```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

### 4. Add Logging Improvements
**Problem:** Inconsistent logging levels and formats

**Fix:** Structured logging
```python
import logging
import json
from pythonjsonlogger import jsonlogger

# Configure structured logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Use structured logging
logger.info("Processing detection", extra={
    "camera_id": camera_id,
    "species": species,
    "confidence": confidence
})
```

## 📋 IMPLEMENTATION PRIORITY

### Phase 1: Critical Security (Do First)
1. ✅ Move hardcoded credentials to environment variables
2. ✅ Restrict CORS settings
3. ✅ Add API key authentication for write operations

### Phase 2: Performance (Do Next)
1. ✅ Configure database connection pooling
2. ✅ Add caching for system health endpoint
3. ✅ Add rate limiting
4. ✅ Add database indexes

### Phase 3: Code Quality (Ongoing)
1. ✅ Split main.py into modules
2. ✅ Add comprehensive input validation
3. ✅ Improve error handling
4. ✅ Add structured logging

## 🔧 Quick Wins (Easy to Implement)

1. **Environment Variables** - 15 minutes
2. **CORS Restrictions** - 5 minutes
3. **Connection Pooling** - 10 minutes
4. **Database Indexes** - 20 minutes
5. **Rate Limiting** - 30 minutes

