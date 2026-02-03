"""Script to check and configure MotionEye webhooks"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MOTIONEYE_URL
from services.motioneye import MotionEyeClient

WEBHOOK_URL = "http://localhost:8001/api/motioneye/webhook"

def check_and_fix_webhooks():
    """Check webhook configuration and offer to fix"""
    client = MotionEyeClient()
    
    print("=" * 60)
    print("MotionEye Webhook Configuration Check")
    print("=" * 60)
    print(f"Webhook URL should be: {WEBHOOK_URL}")
    print()
    
    cameras = client.get_cameras()
    if not cameras:
        print("[ERROR] No cameras found in MotionEye!")
        return
    
    print(f"Found {len(cameras)} cameras\n")
    
    cameras_needing_webhook = []
    
    for camera in cameras:
        camera_id = camera.get("id")
        camera_name = camera.get("name", f"Camera {camera_id}")
        
        try:
            config = client.get_camera_config(camera_id)
            if not config:
                print(f"[ERROR] Camera {camera_id} ({camera_name}): Could not get config")
                continue
            
            on_picture_save = config.get("on_picture_save", "")
            on_movie_end = config.get("on_movie_end", "")
            
            has_webhook = WEBHOOK_URL in on_picture_save or WEBHOOK_URL in on_movie_end
            
            if has_webhook:
                print(f"[OK] Camera {camera_id} ({camera_name}): Webhook configured")
            else:
                print(f"[MISSING] Camera {camera_id} ({camera_name}): Webhook NOT configured")
                cameras_needing_webhook.append((camera_id, camera_name, config))
        except Exception as e:
            print(f"[ERROR] Camera {camera_id} ({camera_name}): {e}")
    
    if cameras_needing_webhook:
        print("\n" + "=" * 60)
        print(f"Found {len(cameras_needing_webhook)} cameras without webhooks")
        print("=" * 60)
        print("\nTo fix webhooks, you have two options:")
        print("\nOption 1: Manual Configuration (Recommended)")
        print("1. Open MotionEye web interface: http://localhost:8765")
        print("2. For each camera listed above:")
        print("   - Click on the camera")
        print("   - Go to 'Advanced' or 'Motion Detection' settings")
        print("   - Find 'on_picture_save' or 'on_movie_end' field")
        print(f"   - Add: curl -X POST {WEBHOOK_URL} -F file_path=%f -F camera_id=%c")
        print("   - Or: wget --post-data \"file_path=%f&camera_id=%c\" -O - " + WEBHOOK_URL)
        print("\nOption 2: Automatic Configuration (via API)")
        print("Note: MotionEye API may require authentication")
        print("This script can attempt to configure webhooks automatically.")
        
        response = input("\nWould you like to try automatic configuration? (y/n): ")
        if response.lower() == 'y':
            configure_webhooks_automatically(client, cameras_needing_webhook)
    else:
        print("\n[OK] All cameras have webhooks configured!")
        print("\nIf detections still aren't working, check:")
        print("1. Motion detection is enabled for cameras")
        print("2. Picture output is enabled (picture_output_motion = on)")
        print("3. Backend is running and accessible")
        print("4. Check backend logs for webhook errors")

def configure_webhooks_automatically(client, cameras_needing_webhook):
    """Attempt to configure webhooks automatically"""
    print("\nAttempting to configure webhooks...")
    
    # MotionEye webhook command format
    webhook_command = f"curl -X POST {WEBHOOK_URL} -F file_path=%f -F camera_id=%c"
    
    success_count = 0
    for camera_id, camera_name, config in cameras_needing_webhook:
        try:
            # Add webhook to on_picture_save if it's empty or doesn't have webhook
            current_on_picture_save = config.get("on_picture_save", "")
            if WEBHOOK_URL not in current_on_picture_save:
                if current_on_picture_save:
                    # Append to existing command
                    config["on_picture_save"] = f"{current_on_picture_save} ; {webhook_command}"
                else:
                    # Set new command
                    config["on_picture_save"] = webhook_command
                
                # Update camera config
                if client.update_camera(camera_id, config):
                    print(f"[OK] Configured webhook for Camera {camera_id} ({camera_name})")
                    success_count += 1
                else:
                    print(f"[ERROR] Failed to update Camera {camera_id} ({camera_name})")
        except Exception as e:
            print(f"[ERROR] Camera {camera_id} ({camera_name}): {e}")
    
    print(f"\nConfigured {success_count} out of {len(cameras_needing_webhook)} cameras")
    if success_count < len(cameras_needing_webhook):
        print("\nSome cameras could not be configured automatically.")
        print("Please configure them manually via MotionEye web interface.")

if __name__ == "__main__":
    check_and_fix_webhooks()
