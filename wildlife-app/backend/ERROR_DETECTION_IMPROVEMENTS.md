# Enhanced Error Detection System

## Overview

The webhook error detection system has been significantly improved to provide better diagnostics, tracking, and troubleshooting capabilities.

## Key Improvements

### 1. Error Categorization

Errors are now automatically categorized into specific types:

- **`file_path_error`**: Issues with file path processing or extraction
- **`database_error`**: Database connection or query failures
- **`speciesnet_error`**: SpeciesNet image processing failures
- **`permission_error`**: File access permission issues
- **`not_found_error`**: Resources (files, cameras) not found
- **`unknown`**: Unclassified errors (with full traceback)

### 2. Enhanced Error Logging

All errors now include:
- **Error Type**: Python exception class name
- **Error Category**: Categorized error type
- **Full Context**: Camera ID, file path, event type, payload details
- **Traceback**: Complete stack trace (in debug mode)
- **Timestamp**: When the error occurred

### 3. Audit Log Integration

All webhook errors are automatically logged to the audit log system with:
- Error details
- Troubleshooting suggestions
- Payload analysis
- Resource information

### 4. Missing Data Detection

When webhooks are missing required data:
- **Payload Analysis**: Lists all available keys in the payload
- **Missing Field Detection**: Identifies which fields are missing (camera_id, file_path)
- **Payload Size**: Helps identify truncated or corrupted payloads

### 5. File Not Found Diagnostics

When image files are not found:
- **Path Mapping**: Shows original path vs. mapped local path
- **Directory Existence**: Checks if parent directories exist
- **Media Directory Check**: Verifies motioneye_media directory exists
- **Path Analysis**: Full path breakdown for debugging

### 6. SpeciesNet Error Detection

SpeciesNet processing errors are now:
- **Caught Early**: Before detection creation
- **Categorized**: Specific error types identified
- **Logged**: Full context preserved
- **Reported**: Clear error messages with suggestions

## Error Response Format

All errors now return structured responses:

```json
{
  "status": "error",
  "error_type": "ValueError",
  "error_category": "file_path_error",
  "message": "Detailed error message",
  "details": {
    "issue": "Human-readable issue description",
    "suggestion": "Troubleshooting suggestion",
    "camera_id": 1,
    "file_path": "/path/to/file.jpg",
    ...
  },
  "timestamp": "2025-12-05T16:00:00"
}
```

## Logging Examples

### Before
```
Error processing MotionEye webhook: cannot access local variable 'file_path'
```

### After
```
❌ MotionEye Webhook Error [file_path_error] - UnboundLocalError: cannot access local variable 'file_path'
  Error Type: UnboundLocalError
  Error Category: file_path_error
  Camera ID: 1
  File Path: /var/lib/motioneye/Camera1/2025-12-05/test.jpg
  Event Type: picture_save
  Suggestion: Check MotionEye webhook payload format and file path extraction logic
```

## Audit Log Entries

All errors create audit log entries with:
- **Action**: `WEBHOOK_ERROR` or `WEBHOOK_IGNORED`
- **Resource Type**: `webhook`
- **Success**: `false`
- **Error Message**: Categorized error description
- **Details**: Full error context and suggestions

## Troubleshooting

### Viewing Errors

1. **Backend Logs**: Check console output for detailed error messages
2. **Audit Logs**: Query `/api/audit` endpoint filtered by `action=WEBHOOK_ERROR`
3. **Error Categories**: Filter by `error_category` in audit log details

### Common Issues

#### Missing Data Errors
- **Symptom**: `WEBHOOK_IGNORED` with `missing_required_data`
- **Check**: MotionEye webhook configuration, payload format
- **Solution**: Verify webhook URL and MotionEye camera settings

#### File Not Found Errors
- **Symptom**: `file_not_found` error category
- **Check**: File path mapping, motioneye_media directory
- **Solution**: Verify Docker volume mounts and file synchronization

#### SpeciesNet Errors
- **Symptom**: `speciesnet_error` category
- **Check**: SpeciesNet server status, image file validity
- **Solution**: Restart SpeciesNet server, verify image format

## Benefits

1. **Faster Diagnosis**: Error categories help identify issues quickly
2. **Better Tracking**: All errors logged to audit system
3. **Actionable Suggestions**: Each error includes troubleshooting tips
4. **Context Preservation**: Full error context maintained for debugging
5. **Pattern Detection**: Categorized errors help identify systemic issues

## Future Enhancements

- Error rate monitoring and alerts
- Automatic error recovery attempts
- Error pattern analysis and reporting
- Integration with monitoring systems
- Error dashboard in frontend

