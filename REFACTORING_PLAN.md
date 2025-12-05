# Complete Refactoring Plan

## Status: In Progress

### Completed ✅
1. ✅ Created `services/events.py` - EventManager extracted
2. ✅ Created `services/photo_scanner.py` - PhotoScanner extracted  
3. ✅ Created `routers/cameras.py` - Camera endpoints (structure created)
4. ✅ Created `routers/system.py` - System health endpoints (already exists)

### In Progress ⏳
Creating all remaining router modules and updating main.py

### Remaining Tasks 📋

#### Router Modules to Create:
1. **routers/detections.py** (~800 lines)
   - GET /detections
   - GET /api/detections
   - POST /detections
   - DELETE /detections/{id}
   - POST /detections/bulk-delete
   - GET /detections/count
   - GET /api/detections/count
   - GET /detections/species-counts
   - GET /detections/unique-species-count
   - POST /process-image
   - GET /api/detections/export

2. **routers/analytics.py** (~400 lines)
   - GET /api/analytics/species
   - GET /api/analytics/timeline
   - GET /api/analytics/cameras
   - GET /analytics/detections/timeseries
   - GET /analytics/detections/top_species

3. **routers/auth.py** (~300 lines)
   - POST /api/auth/register
   - POST /api/auth/login
   - POST /api/auth/logout
   - GET /api/auth/me
   - POST /api/auth/change-password

4. **routers/webhooks.py** (~200 lines)
   - POST /api/webhooks
   - GET /api/webhooks
   - GET /api/webhooks/{id}
   - PUT /api/webhooks/{id}
   - DELETE /api/webhooks/{id}
   - POST /api/webhooks/{id}/test

5. **routers/backups.py** (~150 lines)
   - POST /api/backup/create
   - GET /api/backup/list
   - GET /api/backup/{backup_id}
   - DELETE /api/backup/{backup_id}

6. **routers/config.py** (~100 lines)
   - GET /api/config

7. **routers/notifications.py** (~100 lines)
   - GET /api/notifications/status
   - POST /api/notifications/toggle
   - PUT /api/notifications/enabled

8. **routers/media.py** (~150 lines)
   - GET /media/{camera}/{date}/{filename}
   - GET /archived_photos/{species}/{camera}/{date}/{filename}
   - GET /thumbnails/{filename}
   - GET /api/thingino/image/{detection_id}

9. **routers/events.py** (~100 lines)
   - GET /events/detections
   - GET /events/system

10. **routers/motioneye.py** (~300 lines)
    - POST /api/motioneye/webhook
    - POST /api/thingino/capture
    - POST /api/thingino/webhook

11. **routers/audit.py** (~100 lines)
    - GET /audit-logs
    - GET /api/audit-logs

12. **routers/debug.py** (~200 lines)
    - GET /api/trigger-photo-scan
    - GET /api/photo-scan-status
    - Various debug endpoints

### Final Step
Update main.py to:
1. Import all routers
2. Include all routers with app.include_router()
3. Remove all endpoint definitions
4. Keep only app setup, middleware, startup/shutdown events
5. Import PhotoScanner functions from services.photo_scanner

### Estimated Impact
- **Before**: main.py ~4806 lines
- **After**: main.py ~300-500 lines
- **Reduction**: ~90% reduction in main.py size
- **Total code**: Same, just better organized

