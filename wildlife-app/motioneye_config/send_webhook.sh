#!/bin/bash
# MotionEye webhook script
# This script sends a webhook to the Wildlife App backend when MotionEye saves a picture
# MotionEye calls: on_picture_save <script> %$ %f picture_save %t
# Where: %$ = camera number, %f = file path, %t = timestamp

FILE_PATH="$2"
EVENT_TYPE="${3:-picture_save}"
TIMESTAMP="${4:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}"

# Extract camera number from file path (MotionEye format: /var/lib/motioneye/Camera1/...)
CAMERA_ID=$(echo "$FILE_PATH" | sed -n 's|.*/Camera\([0-9]*\)/.*|\1|p')

# If first argument is provided and looks like a number, use it as camera_id
# MotionEye passes %$ which should be the camera number
if [ -n "$1" ] && [ "$1" != "%$" ] && [ "$1" -eq "$1" ] 2>/dev/null; then
    CAMERA_ID="$1"
fi

# Validate required parameters
if [ -z "$FILE_PATH" ] || [ -z "$CAMERA_ID" ]; then
    echo "$(date): Webhook script ERROR - Missing required parameters. Camera: $CAMERA_ID, File: $FILE_PATH, Args: $@" >> /tmp/webhook_debug.log 2>&1
    exit 1
fi

# Log execution for debugging
echo "$(date): Webhook script called - Camera: $CAMERA_ID, File: $FILE_PATH, Event: $EVENT_TYPE" >> /tmp/webhook_debug.log 2>&1

# Webhook URL
WEBHOOK_URL="http://host.docker.internal:8001/api/motioneye/webhook"

# Escape JSON values to prevent injection
FILE_PATH_ESCAPED=$(echo "$FILE_PATH" | sed 's/"/\\"/g')
EVENT_TYPE_ESCAPED=$(echo "$EVENT_TYPE" | sed 's/"/\\"/g')
TIMESTAMP_ESCAPED=$(echo "$TIMESTAMP" | sed 's/"/\\"/g')

# Prepare JSON payload with proper escaping
PAYLOAD=$(cat <<EOF
{
  "camera_id": $CAMERA_ID,
  "file_path": "$FILE_PATH_ESCAPED",
  "type": "$EVENT_TYPE_ESCAPED",
  "timestamp": "$TIMESTAMP_ESCAPED"
}
EOF
)

# Send webhook (log errors but allow script to continue)
RESPONSE=$(curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time 10 \
  --write-out "\nHTTP_CODE:%{http_code}\n" \
  2>&1)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

# Log the result for debugging
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "$(date): Webhook sent successfully - HTTP $HTTP_CODE, Camera: $CAMERA_ID" >> /tmp/webhook_debug.log 2>&1
else
    echo "$(date): Webhook FAILED - HTTP $HTTP_CODE, Camera: $CAMERA_ID, Response: $RESPONSE_BODY" >> /tmp/webhook_debug.log 2>&1
fi

exit 0

