# SpeciesNet Integration Guide

## Overview

SpeciesNet is now fully integrated into both the **Test Models page** and the **Detection System**. This guide explains how to use it.

## Test Models Page

SpeciesNet will **always appear** in the Test Models page (`/model-test`), even if the SpeciesNet server is not running. If the server is unavailable, it will show an error message indicating that the server needs to be started.

### How to Use SpeciesNet in Test Models

1. **Start the SpeciesNet Server:**
   ```bash
   cd wildlife-app/backend
   python -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000
   ```

2. **Open the Test Models Page:**
   - Navigate to `http://localhost:3000/model-test`
   - SpeciesNet will appear in the list of AI models

3. **Test with Sample Media:**
   - Select an image or video from the sample gallery
   - Click "Test All Models"
   - SpeciesNet results will appear alongside other models

## Detection System Integration

SpeciesNet is fully integrated into the detection system and will be used for processing camera trap images when configured.

### Configuration

Set the `AI_BACKEND` environment variable to use SpeciesNet:

```bash
# In your .env file or environment
AI_BACKEND=speciesnet
```

Or in `wildlife-app/backend/config.py`:
```python
AI_BACKEND = "speciesnet"  # Options: speciesnet, yolov11, yolov8, clip, vit, ensemble
```

### How It Works

1. **MotionEye Webhook Processing:**
   - When MotionEye detects motion, it sends a webhook to the backend
   - The backend uses the configured `AI_BACKEND` to process the image
   - If `AI_BACKEND=speciesnet`, SpeciesNet will be used

2. **Automatic Fallback:**
   - If SpeciesNet server is not available, the system will log a warning
   - The detection will still be processed, but may use a fallback backend
   - Check backend logs to see which backend was actually used

### Verification

To verify SpeciesNet is working with detections:

1. **Check Backend Logs:**
   ```bash
   # Look for these messages:
   # "[OK] SpeciesNet backend registered and available"
   # "Using configured backend: 'speciesnet' (available)"
   ```

2. **Check Detection Results:**
   - Go to the Detections page
   - Look at recent detections
   - SpeciesNet predictions should appear in the species field

3. **Test with Test Models Page:**
   - Use the Test Models page to verify SpeciesNet is responding
   - If it works there, it will work in the detection system

## Troubleshooting

### SpeciesNet Not Appearing in Test Models

- **Check if SpeciesNet server is running:**
  ```bash
  curl http://localhost:8000/health
  ```
  Should return `{"status": "ok"}`

- **Check backend logs:**
  Look for `"[OK] SpeciesNet backend registered and available"` or `"[FAIL] SpeciesNet backend not available"`

### SpeciesNet Not Used in Detections

- **Verify Configuration:**
  ```bash
  # Check config.py or .env
  AI_BACKEND=speciesnet
  ```

- **Check Backend Logs:**
  Look for `"Predicting with backend: 'speciesnet'"` in the logs

- **Restart Backend:**
  After changing `AI_BACKEND`, restart the backend server

### SpeciesNet Server Not Starting

- **Check Port 8000:**
  Make sure port 8000 is not in use by another service

- **Check Dependencies:**
  SpeciesNet requires its dependencies to be installed. See `speciesnet_server.py` for details.

- **Check Logs:**
  Look for initialization errors in the SpeciesNet server logs

## Best Practices

1. **Start SpeciesNet Server First:**
   - Start SpeciesNet server before starting the main backend
   - This ensures it's available when the backend initializes

2. **Use Ensemble for Best Results:**
   - Consider using `AI_BACKEND=ensemble` to combine SpeciesNet with other models
   - This provides the best accuracy

3. **Monitor Performance:**
   - Use the Test Models page to compare SpeciesNet performance with other models
   - Check inference times and accuracy

## Summary

- ✅ SpeciesNet **always appears** in Test Models page
- ✅ SpeciesNet **works with detection system** when configured
- ✅ Automatic fallback if SpeciesNet server unavailable
- ✅ Clear error messages if server not running

