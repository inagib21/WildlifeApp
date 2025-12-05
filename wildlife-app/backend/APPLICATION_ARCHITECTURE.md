# Application Architecture: Setup, Middleware & Router Registration

## Focus: How main.py Organizes the Application

This document focuses specifically on how `main.py` handles **application setup**, **middleware configuration**, and **router registration** - the three core responsibilities of the main application file.

---

## 1. Application Setup

### 1.1 Environment & Configuration Loading

```python
# Lines 40-48
load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

configure_access_logs()  # Setup access logging middleware
```

**What it does:**
- Loads environment variables (database URLs, API keys, etc.)
- Configures Python logging system
- Sets up access logging for HTTP requests

**Why it's here:**
- Must happen before any other initialization
- Required for all subsequent configuration
- Sets up observability (logging)

---

### 1.2 FastAPI Application Instance

```python
# Lines 50-57
app = FastAPI(
    title="Wildlife Detection API",
    description="API for managing wildlife camera detections, cameras, and system monitoring",
    version="1.0.0",
    docs_url="/docs",        # Swagger UI documentation
    redoc_url="/redoc",      # ReDoc documentation
    openapi_url="/openapi.json"  # OpenAPI schema
)
```

**What it does:**
- Creates the main FastAPI application instance
- Configures API metadata for documentation
- Enables automatic API documentation generation

**Configuration Options:**
- `title`: API name (appears in docs)
- `description`: API description (appears in docs)
- `version`: API version
- `docs_url`: Swagger UI endpoint (`/docs`)
- `redoc_url`: ReDoc endpoint (`/redoc`)
- `openapi_url`: OpenAPI JSON schema endpoint

**Result:**
- Application instance ready for middleware and routers
- Automatic API documentation available at `/docs`

---

## 2. Middleware Configuration

Middleware is configured in a specific order. The order matters because middleware executes in reverse order of registration for requests, and in registration order for responses.

### 2.1 Rate Limiting Middleware

```python
# Lines 59-68
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Configuration Details:**

1. **Limiter Instance:**
   ```python
   limiter = Limiter(key_func=get_remote_address)
   ```
   - Creates a rate limiter instance
   - Uses client IP address as the key for rate limiting
   - Each IP address has its own rate limit bucket

2. **App State:**
   ```python
   app.state.limiter = limiter
   ```
   - Stores limiter in app state
   - Makes it accessible throughout the application
   - Required for `@limiter.limit()` decorators to work

3. **Exception Handler:**
   ```python
   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   ```
   - Handles rate limit exceeded errors
   - Returns proper HTTP 429 (Too Many Requests) response
   - Includes retry-after headers

**How It Works:**
- **Global Setup:** Limiter is created once at application startup
- **Per-Endpoint Limits:** Each router receives the `limiter` instance
- **Decorator Usage:** Endpoints use `@limiter.limit("60/minute")` decorators
- **IP-Based:** Limits are enforced per client IP address
- **Automatic:** No manual rate limit checking needed in endpoints

**Example Usage in Routers:**
```python
@router.get("/endpoint")
@limiter.limit("60/minute")  # 60 requests per minute per IP
def my_endpoint(request: Request):
    ...
```

---

### 2.2 API Key Authentication Middleware

```python
# Lines 70-139
security = HTTPBearer(auto_error=False)

def get_api_key(...) -> Optional[str]:
    """Extract API key from request headers"""
    # Supports Authorization: Bearer <key> or X-API-Key: <key>

def verify_api_key(...) -> Optional[Any]:
    """Verify API key if provided (optional authentication)"""
    # Validates key against database
    # Returns None if no key provided (allows public access)
```

**Configuration Details:**

1. **HTTPBearer Security:**
   ```python
   security = HTTPBearer(auto_error=False)
   ```
   - Creates HTTP Bearer token security scheme
   - `auto_error=False`: Doesn't raise errors if no token provided
   - Allows optional authentication

2. **API Key Extraction:**
   ```python
   def get_api_key(
       request: Request,
       authorization: Optional[str] = Header(None, alias="Authorization"),
       x_api_key: Optional[str] = Header(None, alias="X-API-Key")
   ) -> Optional[str]:
   ```
   - Extracts API key from request headers
   - Supports two formats:
     - `Authorization: Bearer <key>`
     - `X-API-Key: <key>`
   - Returns `None` if no key provided (optional auth)

3. **API Key Verification:**
   ```python
   def verify_api_key(
       request: Request,
       api_key: Optional[str] = Depends(get_api_key),
       db: Session = Depends(get_db)
   ) -> Optional[Any]:
   ```
   - Validates API key against database
   - Checks if key is enabled and not expired
   - Tracks client IP address
   - Returns `None` if:
     - `API_KEY_ENABLED` is `False` (auth disabled)
     - No key provided (optional auth)
   - Raises `HTTPException` if key is invalid

**How It Works:**
- **Optional:** Authentication is optional by design
- **Flexible:** Supports multiple header formats
- **Configurable:** Can be disabled via `API_KEY_ENABLED` config
- **Secure:** Validates keys, tracks IPs, supports expiration
- **Dependency Injection:** Used via `Depends(verify_api_key)` in endpoints

**Example Usage in Routers:**
```python
@router.get("/protected")
def protected_endpoint(
    api_key: Optional[Any] = Depends(verify_api_key)
):
    if not api_key:
        # Public access allowed
        ...
    else:
        # Authenticated access
        ...
```

---

### 2.3 CORS Middleware

```python
# Lines 141-150
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # From config (e.g., ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
```

**Configuration Details:**

1. **Allowed Origins:**
   ```python
   allow_origins=ALLOWED_ORIGINS
   ```
   - List of allowed origins from config
   - Example: `["http://localhost:3000", "https://example.com"]`
   - Restricts which domains can make requests
   - **Security:** Prevents unauthorized cross-origin requests

2. **Credentials:**
   ```python
   allow_credentials=True
   ```
   - Allows cookies and authentication headers
   - Required for authenticated requests from frontend
   - Enables session-based authentication

3. **Methods:**
   ```python
   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
   ```
   - Only allows specific HTTP methods
   - Blocks other methods (e.g., PATCH, HEAD)
   - **Security:** Principle of least privilege

4. **Headers:**
   ```python
   allow_headers=["Content-Type", "Authorization", "X-API-Key"]
   ```
   - Only allows specific request headers
   - Blocks custom headers unless explicitly allowed
   - **Security:** Prevents header-based attacks

**How It Works:**
- **Preflight Requests:** Handles OPTIONS requests automatically
- **Origin Validation:** Checks origin against `ALLOWED_ORIGINS`
- **Header Validation:** Validates request headers
- **Method Validation:** Validates HTTP method
- **Automatic:** No manual CORS handling needed in endpoints

**Security Benefits:**
- Prevents CSRF attacks
- Restricts access to known origins
- Limits attack surface
- Follows security best practices

---

## 3. Router Registration

Router registration follows a three-step process: **Import**, **Setup**, **Register**.

### 3.1 Router Imports

```python
# Lines 434-462
try:
    from routers.system import setup_system_router
    from routers.cameras import setup_cameras_router
    from routers.detections import setup_detections_router
    from routers.webhooks import setup_webhooks_router
    from routers.backups import setup_backups_router
    from routers.notifications import setup_notifications_router
    from routers.media import setup_media_router
    from routers.events import setup_events_router
    from routers.config import setup_config_router
    from routers.debug import setup_debug_router
    from routers.analytics import setup_analytics_router
    from routers.auth import setup_auth_router
    from routers.audit import setup_audit_router
except ImportError:
    # Fallback for relative imports (when run as module)
    from .routers.system import setup_system_router
    ...
```

**What it does:**
- Imports router setup functions from all router modules
- Supports both absolute and relative imports
- Handles different execution contexts (direct run vs. module import)

**Why try/except:**
- **Absolute imports:** Work when running directly (`python main.py`)
- **Relative imports:** Work when imported as module (`from backend import main`)
- **Flexibility:** Supports both execution methods

---

### 3.2 Router Setup

```python
# Lines 464-477
system_router = setup_system_router(limiter, get_db)
cameras_router = setup_cameras_router(limiter, get_db)
detections_router = setup_detections_router(limiter, get_db)
webhooks_router = setup_webhooks_router(limiter, get_db)
backups_router = setup_backups_router(limiter, get_db)
notifications_router = setup_notifications_router(limiter, get_db)
media_router = setup_media_router()
events_router = setup_events_router()
config_router = setup_config_router(limiter, get_db)
debug_router = setup_debug_router(get_db)
analytics_router = setup_analytics_router(limiter, get_db)
auth_router = setup_auth_router(limiter, get_db)
audit_router = setup_audit_router(limiter, get_db)
```

**What it does:**
- Calls setup function for each router
- Passes required dependencies to each router
- Returns configured `APIRouter` instances

**Dependency Injection Pattern:**

1. **Routers with Rate Limiting:**
   ```python
   setup_*_router(limiter, get_db)
   ```
   - Receives `limiter` for rate limiting
   - Receives `get_db` for database access
   - Most routers use this pattern

2. **Routers without Rate Limiting:**
   ```python
   setup_media_router()  # No dependencies
   setup_events_router()  # No dependencies
   ```
   - Media router: Read-only, no rate limiting needed
   - Events router: SSE streams, no rate limiting needed

3. **Routers with Partial Dependencies:**
   ```python
   setup_debug_router(get_db)  # Only database, no rate limiting
   ```
   - Debug router: Needs database but no rate limiting
   - Allows debugging without rate limit restrictions

**Setup Function Pattern:**
Each router module follows this pattern:
```python
# routers/example.py
router = APIRouter()

def setup_example_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup router with dependencies"""
    
    @router.get("/endpoint")
    @limiter.limit("60/minute")
    def my_endpoint(request: Request, db: Session = Depends(get_db)):
        ...
    
    return router
```

**Benefits:**
- **Dependency Injection:** Dependencies passed explicitly
- **Testability:** Dependencies can be mocked in tests
- **Flexibility:** Each router can have different dependencies
- **Isolation:** Routers don't depend on global state

---

### 3.3 Router Registration

```python
# Lines 479-491
app.include_router(system_router)
app.include_router(cameras_router)
app.include_router(detections_router)
app.include_router(webhooks_router)
app.include_router(backups_router)
app.include_router(notifications_router)
app.include_router(media_router)
app.include_router(events_router)
app.include_router(config_router)
app.include_router(debug_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(audit_router)
```

**What it does:**
- Registers all routers with the FastAPI application
- Makes all endpoints available
- Maintains endpoint paths as defined in routers

**How FastAPI Processes Routers:**

1. **Route Discovery:**
   - FastAPI scans all registered routers
   - Discovers all endpoints and their decorators
   - Builds route table

2. **Path Resolution:**
   - Router paths are preserved as defined
   - Example: `@router.get("/cameras")` becomes `GET /cameras`
   - No path prefix needed (can be added if desired)

3. **Middleware Application:**
   - All middleware applies to all routes
   - Rate limiting, CORS, authentication all work automatically
   - No per-route middleware configuration needed

4. **Documentation Generation:**
   - All routes appear in `/docs`
   - OpenAPI schema includes all endpoints
   - Automatic API documentation

**Registration Order:**
- Order doesn't matter for most cases
- FastAPI handles route conflicts (first match wins)
- All routers are registered before application starts

**Result:**
- All 13 routers active
- All endpoints accessible
- All middleware applied
- Complete API documentation

---

## Middleware Execution Order

Understanding middleware execution order is crucial for debugging and understanding request flow.

### Request Flow (Incoming Request)

```
1. CORS Middleware
   ↓
2. Rate Limiting (via decorators)
   ↓
3. API Key Authentication (via Depends)
   ↓
4. Router Endpoint Handler
   ↓
5. Response Generation
```

### Response Flow (Outgoing Response)

```
1. Router Endpoint Response
   ↓
2. API Key Authentication (cleanup)
   ↓
3. Rate Limiting (tracking)
   ↓
4. CORS Middleware (adds headers)
   ↓
5. HTTP Response
```

**Key Points:**
- **CORS:** Executes first and last (handles preflight and adds headers)
- **Rate Limiting:** Applied via decorators, checked before endpoint
- **Authentication:** Applied via `Depends()`, checked before endpoint
- **Endpoint:** Executes after all middleware passes

---

## Dependency Injection Flow

Understanding how dependencies flow through the application:

```
main.py
  ├── Creates: limiter, get_db, verify_api_key
  │
  ├── Passes to: setup_*_router(limiter, get_db)
  │
  └── Router Setup
      ├── Receives: limiter, get_db
      │
      ├── Creates: router = APIRouter()
      │
      ├── Defines: @router.get("/endpoint")
      │   ├── @limiter.limit("60/minute")
      │   └── def endpoint(request: Request, db: Session = Depends(get_db))
      │
      └── Returns: router
          │
          └── Registered: app.include_router(router)
```

**Dependency Chain:**
1. `main.py` creates dependencies
2. Dependencies passed to router setup functions
3. Routers use dependencies in endpoint decorators
4. FastAPI injects dependencies at request time
5. Endpoints receive dependencies automatically

---

## Complete Initialization Sequence

Understanding the complete startup sequence:

```
1. Import Dependencies
   ├── FastAPI, SQLAlchemy, etc.
   ├── Config, Database, Models
   └── Services (motioneye, speciesnet, etc.)

2. Load Environment
   └── load_dotenv()

3. Configure Logging
   ├── logging.basicConfig()
   └── configure_access_logs()

4. Create FastAPI App
   └── app = FastAPI(...)

5. Configure Middleware
   ├── Rate Limiting
   ├── API Key Authentication
   └── CORS

6. Create Dependencies
   ├── get_db()
   └── verify_api_key()

7. Initialize Services
   ├── Event Manager
   └── Camera Sync Service

8. Setup Database
   └── Base.metadata.create_all()

9. Import Routers
   └── from routers.* import setup_*_router

10. Setup Routers
    └── router = setup_*_router(limiter, get_db)

11. Register Routers
    └── app.include_router(router)

12. Startup Event
    ├── Start EventManager
    ├── Start Camera Sync
    ├── Verify Database
    ├── Run Migrations
    └── Start Photo Scanner

13. Application Ready
    └── All endpoints available
```

---

## Key Design Decisions

### 1. Why Router Setup Functions?

**Decision:** Use `setup_*_router()` functions instead of direct router instances

**Benefits:**
- Dependency injection (pass dependencies explicitly)
- Testability (can mock dependencies)
- Flexibility (different dependencies per router)
- Isolation (routers don't depend on global state)

**Alternative (Not Used):**
```python
# Direct router creation (not used)
router = APIRouter()
@router.get("/endpoint")
def endpoint():
    # How to get limiter? How to get get_db?
    ...
```

### 2. Why Separate Middleware Configuration?

**Decision:** Configure middleware in `main.py` before router registration

**Benefits:**
- Centralized configuration
- Easy to see all middleware at once
- Consistent application-wide behavior
- Easy to enable/disable features

**Alternative (Not Used):**
```python
# Per-router middleware (not used)
@router.middleware("http")
async def my_middleware(request, call_next):
    ...
```

### 3. Why Dependency Functions?

**Decision:** Use dependency functions (`get_db`, `verify_api_key`) instead of direct access

**Benefits:**
- Automatic lifecycle management
- Testability (can override in tests)
- Reusability (used across all routers)
- FastAPI best practices

**Alternative (Not Used):**
```python
# Direct database access (not used)
db = SessionLocal()
# Who closes it? What about errors?
```

---

## Summary

The `main.py` file is now focused on three core responsibilities:

1. **Application Setup:**
   - Environment loading
   - Logging configuration
   - FastAPI app creation

2. **Middleware Configuration:**
   - Rate limiting (global setup, per-endpoint limits)
   - API key authentication (optional, flexible)
   - CORS (security-focused)

3. **Router Registration:**
   - Import router setup functions
   - Setup routers with dependencies
   - Register routers with application

This architecture provides:
- ✅ **Clear separation of concerns**
- ✅ **Easy to understand and maintain**
- ✅ **Scalable and extensible**
- ✅ **Follows FastAPI best practices**
- ✅ **Testable and mockable**

The result is a clean, maintainable codebase where `main.py` serves as the **orchestration layer** that brings together all the pieces of the application.

