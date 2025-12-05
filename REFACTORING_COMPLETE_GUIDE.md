# Complete Refactoring Guide - Final Steps

## Current Status
- ✅ EventManager extracted to `services/events.py`
- ✅ PhotoScanner extracted to `services/photo_scanner.py`
- ✅ Routers included: system, cameras
- ✅ main.py reduced from 4806 to 4154 lines (~650 lines, 13.5% reduction)

## Remaining Work to Reach Target (~300-500 lines in main.py)

### Detection Endpoints Found (17 endpoints):
1. `GET /detections` - Get all detections with filters
2. `GET /api/detections` - Alias for /detections
3. `POST /detections` - Create detection
4. `DELETE /detections/{detection_id}` - Delete detection
5. `POST /detections/bulk-delete` - Bulk delete
6. `GET /detections/count` - Get count
7. `GET /api/detections/count` - Alias
8. `GET /detections/species-counts` - Species counts
9. `GET /detections/unique-species-count` - Unique species count
10. `POST /process-image` - Process image with SpeciesNet
11. `GET /api/detections/export` - Export detections (CSV/JSON/PDF)
12. `GET /analytics/detections/timeseries` - Timeseries analytics
13. `GET /analytics/detections/top_species` - Top species
14. `GET /analytics/detections/unique_species_count` - Unique species count
15. `GET /api/debug/speciesnet-response/{detection_id}` - Debug endpoint
16. `GET /api/debug/detection-media/{detection_id}` - Debug endpoint
17. `GET /api/thingino/image/{detection_id}` - Thingino image

### Other Endpoints to Extract:
- Analytics endpoints (~5 endpoints)
- Auth endpoints (~5 endpoints)
- Webhook endpoints (~6 endpoints)
- Backup endpoints (~4 endpoints)
- Config endpoints (~1 endpoint)
- Notification endpoints (~3 endpoints)
- Media endpoints (~4 endpoints)
- Events/SSE endpoints (~2 endpoints)
- MotionEye webhook endpoints (~3 endpoints)
- Audit log endpoints (~2 endpoints)
- Debug endpoints (~5 endpoints)

## Next Steps

Due to the large scope (~2900 lines to extract), I recommend:

**Option 1: Complete All Routers Now** (Will take multiple steps)
- Create all router modules systematically
- Update main.py to use all routers
- Remove all endpoint definitions from main.py
- Test everything

**Option 2: Incremental Approach** (Recommended)
- Create routers for the largest endpoint groups first (detections, analytics)
- Update main.py incrementally
- Test after each major group
- Continue with remaining routers

**Option 3: Manual Completion**
- Use this guide to create remaining routers following the pattern
- Pattern: See `routers/cameras.py` and `routers/system.py` for examples

## Router Creation Pattern

Each router should:
1. Import dependencies (APIRouter, HTTPException, etc.)
2. Create router instance
3. Define `setup_*_router(limiter, get_db)` function
4. Register all endpoints with `@router.*` decorators
5. Return router

Then in main.py:
```python
from routers.detections import setup_detections_router
detections_router = setup_detections_router(limiter, get_db)
app.include_router(detections_router)
```

## Estimated Final Structure

```
main.py (~300-500 lines)
├── App setup
├── Middleware
├── Router includes
└── Startup/shutdown events

routers/
├── system.py ✅
├── cameras.py ✅
├── detections.py (to create)
├── analytics.py (to create)
├── auth.py (to create)
├── webhooks.py (to create)
├── backups.py (to create)
├── config.py (to create)
├── notifications.py (to create)
├── media.py (to create)
├── events.py (to create)
├── motioneye.py (to create)
├── audit.py (to create)
└── debug.py (to create)

services/
├── events.py ✅
├── photo_scanner.py ✅
└── (other existing services)
```

