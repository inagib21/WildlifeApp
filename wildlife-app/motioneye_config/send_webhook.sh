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

# Log execution for debugging (remove in production)
echo "$(date): Webhook script called - Camera: $CAMERA_ID, File: $FILE_PATH" >> /tmp/webhook_debug.log 2>&1

# Webhook URL
WEBHOOK_URL="http://host.docker.internal:8001/api/motioneye/webhook"

# Prepare JSON payload
PAYLOAD=$(cat <<EOF
{
  "camera_id": ${CAMERA_ID:-null},
  "file_path": "${FILE_PATH}",
  "type": "${EVENT_TYPE}",
  "timestamp": "${TIMESTAMP}"
}
EOF
)

# Send webhook (suppress output but allow errors to be logged)
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time 10 \
  --silent \
  --fail \
  2>&1

exit 0

