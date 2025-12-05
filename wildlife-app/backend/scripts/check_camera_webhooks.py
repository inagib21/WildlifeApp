"""Script to check camera webhook configuration and detection status"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MOTIONEYE_URL
from services.motioneye import MotionEyeClient
import requests

def check_camera_webhooks():
    """Check which cameras have webhooks configured and are detecting"""
    client = MotionEyeClient()
    
    print("=" * 60)
    print("Camera Detection Status Check")
    print("=" * 60)
    
    # Get all cameras from MotionEye
    cameras = client.get_cameras()
    
    if not cameras:
        print("❌ No cameras found in MotionEye!")
        print(f"   MotionEye URL: {MOTIONEYE_URL}")
        return
    
    print(f"\nFound {len(cameras)} cameras in MotionEye\n")
    
    for camera in cameras:
        camera_id = camera.get("id")
        camera_name = camera.get("name", f"Camera {camera_id}")
        motion_detection = camera.get("motion_detection", False)
        
        # Get full config
        config = client.get_camera_config(camera_id)
        
        if not config:
            print(f"❌ Camera {camera_id} ({camera_name}): Could not get config")
            continue
        
        # Check webhook configuration
        on_picture_save = config.get("on_picture_save", "")
        on_movie_end = config.get("on_movie_end", "")
        has_webhook = "webhook" in on_picture_save.lower() or "webhook" in on_movie_end.lower()
        
        # Check motion detection settings
        threshold = config.get("threshold", 0)
        picture_output = config.get("picture_output", "off")
        picture_output_motion = config.get("picture_output_motion", "off")
        
        # Status indicators
        status_icons = []
        if motion_detection:
            status_icons.append("✅ Motion Detection ON")
        else:
            status_icons.append("❌ Motion Detection OFF")
        
        if has_webhook:
            status_icons.append("✅ Webhook Configured")
        else:
            status_icons.append("❌ Webhook NOT Configured")
        
        if picture_output == "on" or picture_output_motion == "on":
            status_icons.append("✅ Picture Output ON")
        else:
            status_icons.append("❌ Picture Output OFF")
        
        print(f"\n📹 Camera {camera_id}: {camera_name}")
        print(f"   {' | '.join(status_icons)}")
        print(f"   Threshold: {threshold}")
        print(f"   Picture Output: {picture_output}")
        print(f"   Picture Output Motion: {picture_output_motion}")
        
        if has_webhook:
            # Extract webhook URL
            webhook_line = on_picture_save if "webhook" in on_picture_save.lower() else on_movie_end
            if "webhook" in webhook_line.lower():
                # Try to extract URL
                if "localhost:8001" in webhook_line:
                    print(f"   ✅ Webhook points to backend (localhost:8001)")
                else:
                    print(f"   ⚠️  Webhook URL: {webhook_line[:100]}...")
        else:
            print(f"   ❌ No webhook found in on_picture_save or on_movie_end")
            print(f"      on_picture_save: {on_picture_save[:80] if on_picture_save else 'empty'}...")
            print(f"      on_movie_end: {on_movie_end[:80] if on_movie_end else 'empty'}...")
    
    print("\n" + "=" * 60)
    print("Recommendations:")
    print("=" * 60)
    print("1. Ensure 'motion_detection' is 'on' for all cameras")
    print("2. Ensure 'picture_output' or 'picture_output_motion' is 'on'")
    print("3. Ensure webhook is configured in 'on_picture_save' or 'on_movie_end'")
    print("4. Check that webhook URL points to: http://localhost:8001/api/motioneye/webhook")
    print("5. Lower threshold if cameras are not detecting motion")
    print("=" * 60)

if __name__ == "__main__":
    check_camera_webhooks()

