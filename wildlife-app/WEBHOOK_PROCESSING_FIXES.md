# Webhook Processing Fixes

## Issues Fixed

### 1. ✅ SpeciesNet Timeout Increased
**Problem**: SpeciesNet timeout was too short (60 seconds), causing timeouts on slower images.

**Fix**: 
- Increased timeout from 60s to 120s for image processing
- This gives SpeciesNet more time to process complex images

**File**: `wildlife-app/backend/services/speciesnet.py`

### 2. ✅ Fallback Detection Creation
**Problem**: When SpeciesNet failed or timed out, no detection was created, even though MotionEye sent a webhook.

**Fix**:
- Added fallback detection creation when SpeciesNet fails
- Creates a detection with "Unknown (SpeciesNet Error)" species
- Still saves the image and creates a detection record
- Broadcasts the detection to connected clients
- Logs the error for debugging

**File**: `wildlife-app/backend/routers/webhooks.py`

### 3. ✅ Blank Detection Handling
**Problem**: Blank detections were being saved (which is correct), but the concern was they might be filtered.

**Fix**:
- Confirmed blank detections are NOT filtered out
- Added comment clarifying that blank detections are valid and should be saved
- Blank detections indicate "no wildlife detected" which is useful information

**File**: `wildlife-app/backend/services/smart_detection.py`

### 4. ✅ Better Error Recovery
**Problem**: Webhook processing would fail completely if SpeciesNet had issues.

**Fix**:
- SpeciesNet errors no longer stop webhook processing
- Fallback detections are created to ensure webhooks result in database records
- Better error logging and tracking
- Webhooks are no longer lost due to SpeciesNet issues

## How It Works Now

### Normal Flow (SpeciesNet Success):
1. MotionEye sends webhook
2. Image is processed by SpeciesNet
3. Smart detection processor analyzes results
4. Detection is saved to database
5. Detection is broadcast to clients

### Fallback Flow (SpeciesNet Failure):
1. MotionEye sends webhook
2. SpeciesNet processing fails or times out
3. **NEW**: Fallback detection is created with "Unknown (SpeciesNet Error)"
4. Detection is saved to database (ensuring webhook isn't lost)
5. Detection is broadcast to clients
6. Error is logged for debugging

## Benefits

1. **No Lost Webhooks**: Every webhook from MotionEye now creates a detection, even if SpeciesNet fails
2. **Better Debugging**: Errors are logged with full context
3. **Faster Recovery**: System continues working even when SpeciesNet has issues
4. **More Reliable**: Increased timeout reduces false timeouts

## Monitoring

To check if fallback detections are being created:
```bash
cd wildlife-app/backend
python -c "from database import SessionLocal, Detection; db = SessionLocal(); count = db.query(Detection).filter(Detection.species.like('%SpeciesNet Error%')).count(); print(f'Fallback detections: {count}')"
```

## Next Steps

1. Monitor webhook processing logs for SpeciesNet errors
2. Check if SpeciesNet server needs optimization if timeouts persist
3. Consider adding retry logic for transient SpeciesNet errors
4. Monitor fallback detection count to track SpeciesNet reliability

