# How Detections Are Created

## Overview
Detections are created automatically when cameras detect motion and capture images. The system processes these images through AI classification to identify wildlife.

## Detection Creation Flow

### 1. **MotionEye Cameras** (Primary Source)
**Location**: `wildlife-app/backend/routers/webhooks.py` - `/api/motioneye/webhook`

**Process**:
1. Camera detects motion → MotionEye captures image
2. MotionEye sends webhook to backend (`/api/motioneye/webhook`)
3. Backend receives webhook with image file path
4. Image is processed by **SpeciesNet** AI service
5. **Smart Detection Processor** analyzes the results
6. Detection is saved to database
7. Detection is broadcast to connected clients via SSE

**Key Files**:
- `routers/webhooks.py` - Webhook endpoint handler
- `services/speciesnet.py` - AI image classification
- `services/smart_detection.py` - Enhanced detection analysis

### 2. **Thingino Cameras** (Alternative Source)
**Location**: `wildlife-app/backend/routers/webhooks.py` - `/api/thingino/webhook`

**Process**:
1. Thingino camera detects motion
2. Sends webhook with image URL
3. Backend downloads image from camera
4. Processes through SpeciesNet
5. Saves detection to database

### 3. **Photo Scanner Service** (Batch Processing)
**Location**: `wildlife-app/backend/services/photo_scanner.py`

**Process**:
- Scans existing images in `archived_photos` directory
- Processes unprocessed images
- Creates detections for images that haven't been classified yet

### 4. **Manual Detection Creation** (API)
**Location**: `wildlife-app/backend/routers/detections.py` - `POST /api/detections`

**Process**:
- Allows manual creation via API
- Used for testing or importing existing data

## Detection Creation Components

### SpeciesNet Service
- **Purpose**: AI image classification
- **Input**: Image file path
- **Output**: Species predictions with confidence scores
- **Timeout**: 120 seconds (recently increased from 60s)

### Smart Detection Processor
- **Purpose**: Enhanced analysis and filtering
- **Features**:
  - Confidence threshold checking (minimum 0.15)
  - Species name normalization
  - Temporal context analysis (recent detections)
  - Quality assessment
- **Decision**: Determines if detection should be saved

### Database Model
**Location**: `wildlife-app/backend/database.py`

**Detection Fields**:
- `id` - Unique identifier
- `camera_id` - Which camera detected it
- `timestamp` - When it was detected
- `species` - What was detected (e.g., "Human", "Deer", "Blank")
- `confidence` - AI confidence score (0.0 to 1.0)
- `image_path` - Path to the image file
- `file_size`, `image_width`, `image_height` - Image metadata

## Detection Filtering

### What Gets Saved:
✅ Confidence >= 0.15 (minimum threshold)
✅ Blank detections (indicate no wildlife)
✅ All species types (human, vehicle, wildlife, etc.)
✅ Fallback detections (when SpeciesNet fails)

### What Gets Filtered Out:
❌ Confidence < 0.15
❌ Unknown species with confidence < 0.2
❌ Errors in analysis

## Recent Improvements

1. **Fallback Detection Creation**: If SpeciesNet fails, a detection is still created with "Unknown (SpeciesNet Error)"
2. **Increased Timeout**: SpeciesNet timeout increased to 120 seconds
3. **Better Error Handling**: Webhooks no longer fail completely if SpeciesNet has issues

## Monitoring Detection Creation

### Check Recent Detections:
```bash
cd wildlife-app/backend
python get_last_detection.py
```

### Check Detection Activity:
```bash
cd wildlife-app/backend
python check_detections_status.py
```

### View Webhook Processing:
- Check backend logs for webhook processing
- Look for "✅ Detection created in database" messages
- Check audit logs for filtered detections

## Summary

**What Makes Detections:**
1. **MotionEye cameras** → Webhook → SpeciesNet → Database (Primary)
2. **Thingino cameras** → Webhook → SpeciesNet → Database
3. **Photo Scanner** → Batch processing → Database
4. **Manual API** → Direct creation → Database

**Key Services:**
- **SpeciesNet**: AI classification (identifies what's in the image)
- **Smart Detection Processor**: Analyzes and filters results
- **Webhook Handler**: Receives and processes camera events

The system is fully automated - cameras detect motion, images are classified by AI, and detections are automatically saved to the database.

