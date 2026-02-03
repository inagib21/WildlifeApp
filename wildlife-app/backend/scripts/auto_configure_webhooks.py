"""Script to automatically configure MotionEye webhooks for all cameras"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MOTIONEYE_URL
from services.motioneye import MotionEyeClient

WEBHOOK_URL = "http://localhost:8001/api/motioneye/webhook"
WEBHOOK_COMMAND = f"curl -X POST {WEBHOOK_URL} -F file_path=%f -F camera_id=%c"

def configure_webhooks_for_all_cameras():
    """Configure webhooks for all cameras in MotionEye"""
    print("=" * 60)
    print("Automatic Webhook Configuration")
    print("=" * 60)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Webhook Command: {WEBHOOK_COMMAND}")
    print()
    
    # Try with authentication (admin:admin is default)
    # If auth is disabled, this will still work
    client = MotionEyeClient(username="admin", password="admin")
    
    # Get all cameras
    cameras = client.get_cameras()
    if not cameras:
        print("[ERROR] No cameras found in MotionEye!")
        return
    
    print(f"Found {len(cameras)} cameras\n")
    
    success_count = 0
    failed_count = 0
    already_configured = 0
    
    for camera in cameras:
        camera_id = camera.get("id")
        camera_name = camera.get("name", f"Camera {camera_id}")
        
        try:
            # Get current camera configuration
            config = client.get_camera_config(camera_id)
            if not config:
                print(f"[ERROR] Camera {camera_id} ({camera_name}): Could not get config")
                failed_count += 1
                continue
            
            # Check if webhook is already configured
            on_picture_save = config.get("on_picture_save", "")
            on_movie_end = config.get("on_movie_end", "")
            
            has_webhook = WEBHOOK_URL in on_picture_save or WEBHOOK_URL in on_movie_end
            
            if has_webhook:
                print(f"[SKIP] Camera {camera_id} ({camera_name}): Webhook already configured")
                already_configured += 1
                continue
            
            # Prepare webhook command
            # If on_picture_save already has content, append with semicolon
            if on_picture_save and on_picture_save.strip():
                # Check if it already contains our webhook (might be slightly different format)
                if WEBHOOK_URL not in on_picture_save:
                    new_on_picture_save = f"{on_picture_save} ; {WEBHOOK_COMMAND}"
                else:
                    print(f"[SKIP] Camera {camera_id} ({camera_name}): Webhook already present (different format)")
                    already_configured += 1
                    continue
            else:
                new_on_picture_save = WEBHOOK_COMMAND
            
            # Update configuration
            config["on_picture_save"] = new_on_picture_save
            
            # Also ensure motion detection and picture output are enabled
            if config.get("motion_detection") != True:
                config["motion_detection"] = True
                print(f"   [INFO] Enabling motion detection for Camera {camera_id}")
            
            if config.get("picture_output_motion") != "on":
                config["picture_output_motion"] = "on"
                print(f"   [INFO] Enabling picture output motion for Camera {camera_id}")
            
            # Update camera configuration
            if client.update_camera(camera_id, config):
                print(f"[OK] Camera {camera_id} ({camera_name}): Webhook configured successfully")
                success_count += 1
            else:
                print(f"[ERROR] Camera {camera_id} ({camera_name}): Failed to update configuration")
                failed_count += 1
                
        except Exception as e:
            print(f"[ERROR] Camera {camera_id} ({camera_name}): {e}")
            failed_count += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("Configuration Summary")
    print("=" * 60)
    print(f"Total cameras: {len(cameras)}")
    print(f"Successfully configured: {success_count}")
    print(f"Already configured: {already_configured}")
    print(f"Failed: {failed_count}")
    print()
    
    if success_count > 0:
        print("[SUCCESS] Webhooks have been configured!")
        print("Next steps:")
        print("1. Test by triggering motion detection on a camera")
        print("2. Check backend logs for webhook processing")
        print("3. Check Detections page for new entries")
    
    if failed_count > 0:
        print("[WARN] Some cameras could not be configured automatically.")
        print("This might be due to:")
        print("- MotionEye API authentication requirements")
        print("- Camera configuration restrictions")
        print("- Network connectivity issues")
        print()
        print("You can configure these cameras manually:")
        print("1. Open MotionEye: http://localhost:8765")
        print("2. For each failed camera, add this to 'on_picture_save':")
        print(f"   {WEBHOOK_COMMAND}")
    
    print("=" * 60)

def verify_webhook_configuration():
    """Verify webhook configuration for all cameras"""
    print("\n" + "=" * 60)
    print("Verifying Webhook Configuration")
    print("=" * 60)
    
    client = MotionEyeClient()
    cameras = client.get_cameras()
    
    if not cameras:
        print("[ERROR] No cameras found")
        return
    
    configured = 0
    not_configured = []
    
    for camera in cameras:
        camera_id = camera.get("id")
        camera_name = camera.get("name", f"Camera {camera_id}")
        
        try:
            config = client.get_camera_config(camera_id)
            if not config:
                not_configured.append((camera_id, camera_name, "Could not get config"))
                continue
            
            on_picture_save = config.get("on_picture_save", "")
            on_movie_end = config.get("on_movie_end", "")
            
            has_webhook = WEBHOOK_URL in on_picture_save or WEBHOOK_URL in on_movie_end
            
            if has_webhook:
                print(f"[OK] Camera {camera_id} ({camera_name}): Webhook configured")
                configured += 1
            else:
                print(f"[MISSING] Camera {camera_id} ({camera_name}): Webhook NOT configured")
                not_configured.append((camera_id, camera_name, "No webhook found"))
        except Exception as e:
            print(f"[ERROR] Camera {camera_id} ({camera_name}): {e}")
            not_configured.append((camera_id, camera_name, str(e)))
    
    print(f"\nConfigured: {configured}/{len(cameras)}")
    if not_configured:
        print(f"\nCameras needing configuration: {len(not_configured)}")
        for cam_id, cam_name, reason in not_configured:
            print(f"  - Camera {cam_id} ({cam_name}): {reason}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Configure MotionEye webhooks")
    parser.add_argument("--verify-only", action="store_true", 
                       help="Only verify webhook configuration, don't configure")
    args = parser.parse_args()
    
    if args.verify_only:
        verify_webhook_configuration()
    else:
        configure_webhooks_for_all_cameras()
        verify_webhook_configuration()
