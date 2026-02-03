"""Generate webhook configuration files and templates for MotionEye cameras"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MOTIONEYE_URL
from services.motioneye import MotionEyeClient

WEBHOOK_URL = "http://localhost:8001/api/motioneye/webhook"
WEBHOOK_COMMAND = f"curl -X POST {WEBHOOK_URL} -F file_path=%f -F camera_id=%c"

def generate_webhook_config_files():
    """Generate webhook configuration for all cameras"""
    print("=" * 60)
    print("Webhook Configuration Generator")
    print("=" * 60)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print()
    
    client = MotionEyeClient()
    cameras = client.get_cameras()
    
    if not cameras:
        print("[ERROR] No cameras found in MotionEye!")
        return
    
    print(f"Found {len(cameras)} cameras\n")
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webhook_configs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate configuration for each camera
    configs = []
    
    for camera in cameras:
        camera_id = camera.get("id")
        camera_name = camera.get("name", f"Camera {camera_id}")
        
        config = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "webhook_command": WEBHOOK_COMMAND,
            "instructions": [
                f"1. Open MotionEye: {MOTIONEYE_URL}",
                f"2. Click on camera: {camera_name} (ID: {camera_id})",
                "3. Go to 'Motion Detection' or 'Advanced' settings",
                "4. Find 'on_picture_save' field",
                f"5. Paste: {WEBHOOK_COMMAND}",
                "6. Ensure Motion Detection is ON",
                "7. Ensure Picture Output Motion is ON",
                "8. Save settings"
            ]
        }
        configs.append(config)
        
        # Save individual config file
        config_file = os.path.join(output_dir, f"camera_{camera_id}_{camera_name.replace(' ', '_')}.json")
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"[OK] Generated config for Camera {camera_id} ({camera_name})")
    
    # Generate master config file
    master_config = {
        "webhook_url": WEBHOOK_URL,
        "webhook_command": WEBHOOK_COMMAND,
        "total_cameras": len(cameras),
        "cameras": configs
    }
    
    master_file = os.path.join(output_dir, "all_cameras_webhook_config.json")
    with open(master_file, 'w') as f:
        json.dump(master_config, f, indent=2)
    
    # Generate shell script for manual configuration
    generate_shell_script(output_dir, configs)
    
    # Generate PowerShell script
    generate_powershell_script(output_dir, configs)
    
    print(f"\n[SUCCESS] Generated configuration files in: {output_dir}")
    print(f"\nFiles created:")
    print(f"  - all_cameras_webhook_config.json (master config)")
    print(f"  - configure_webhooks.sh (Linux/Mac script)")
    print(f"  - configure_webhooks.ps1 (Windows PowerShell script)")
    print(f"  - Individual camera config files (camera_*.json)")
    
    return output_dir

def generate_shell_script(output_dir, configs):
    """Generate shell script for webhook configuration"""
    script_content = f"""#!/bin/bash
# MotionEye Webhook Configuration Script
# Generated automatically - run this script to see configuration instructions

WEBHOOK_URL="{WEBHOOK_URL}"
WEBHOOK_CMD="{WEBHOOK_COMMAND}"

echo "============================================================"
echo "MotionEye Webhook Configuration"
echo "============================================================"
echo ""
echo "Webhook URL: $WEBHOOK_URL"
echo "Webhook Command: $WEBHOOK_CMD"
echo ""
echo "Total cameras: {len(configs)}"
echo ""
echo "For each camera, add this to 'on_picture_save' in MotionEye:"
echo "$WEBHOOK_CMD"
echo ""
echo "Cameras to configure:"
"""
    
    for config in configs:
        script_content += f"echo \"  - Camera {config['camera_id']}: {config['camera_name']}\"\n"
    
    script_content += """
echo ""
echo "To configure manually:"
echo "1. Open MotionEye: http://localhost:8765"
echo "2. For each camera listed above:"
echo "   - Click on the camera"
echo "   - Go to 'Motion Detection' settings"
echo "   - Find 'on_picture_save' field"
echo "   - Paste the webhook command"
echo "   - Save settings"
echo ""
"""
    
    script_file = os.path.join(output_dir, "configure_webhooks.sh")
    with open(script_file, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_file, 0o755)

def generate_powershell_script(output_dir, configs):
    """Generate PowerShell script for webhook configuration"""
    script_content = f"""# MotionEye Webhook Configuration Script
# Generated automatically - run this script to see configuration instructions

$WEBHOOK_URL = "{WEBHOOK_URL}"
$WEBHOOK_CMD = "{WEBHOOK_COMMAND}"

Write-Host "============================================================"
Write-Host "MotionEye Webhook Configuration"
Write-Host "============================================================"
Write-Host ""
Write-Host "Webhook URL: $WEBHOOK_URL"
Write-Host "Webhook Command: $WEBHOOK_CMD"
Write-Host ""
Write-Host "Total cameras: {len(configs)}"
Write-Host ""
Write-Host "For each camera, add this to 'on_picture_save' in MotionEye:"
Write-Host $WEBHOOK_CMD
Write-Host ""
Write-Host "Cameras to configure:"
"""
    
    for config in configs:
        script_content += f"Write-Host \"  - Camera {config['camera_id']}: {config['camera_name']}\"\n"
    
    script_content += """
Write-Host ""
Write-Host "To configure manually:"
Write-Host "1. Open MotionEye: http://localhost:8765"
Write-Host "2. For each camera listed above:"
Write-Host "   - Click on the camera"
Write-Host "   - Go to 'Motion Detection' settings"
Write-Host "   - Find 'on_picture_save' field"
Write-Host "   - Paste the webhook command"
Write-Host "   - Save settings"
Write-Host ""
Write-Host "Press any key to open MotionEye in your browser..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
Start-Process "http://localhost:8765"
"""
    
    script_file = os.path.join(output_dir, "configure_webhooks.ps1")
    with open(script_file, 'w') as f:
        f.write(script_content)

def generate_bulk_config_template():
    """Generate a template for bulk configuration"""
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webhook_configs")
    os.makedirs(output_dir, exist_ok=True)
    
    template = {
        "instructions": "Copy this webhook command to each camera's 'on_picture_save' field in MotionEye",
        "webhook_command": WEBHOOK_COMMAND,
        "webhook_url": WEBHOOK_URL,
        "quick_copy": WEBHOOK_COMMAND
    }
    
    template_file = os.path.join(output_dir, "webhook_command_template.txt")
    with open(template_file, 'w') as f:
        f.write(f"MotionEye Webhook Command\n")
        f.write("=" * 60 + "\n\n")
        f.write("Copy and paste this command into each camera's 'on_picture_save' field:\n\n")
        f.write(WEBHOOK_COMMAND + "\n\n")
        f.write("=" * 60 + "\n")
        f.write("Instructions:\n")
        f.write("1. Open MotionEye: http://localhost:8765\n")
        f.write("2. For each camera:\n")
        f.write("   - Click on the camera\n")
        f.write("   - Go to 'Motion Detection' settings\n")
        f.write("   - Find 'on_picture_save' field\n")
        f.write("   - Paste the command above\n")
        f.write("   - Save settings\n")
    
    print(f"[OK] Generated template file: {template_file}")

if __name__ == "__main__":
    output_dir = generate_webhook_config_files()
    generate_bulk_config_template()
    
    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print(f"1. Review configuration files in: {output_dir}")
    print("2. Run the PowerShell script: .\\webhook_configs\\configure_webhooks.ps1")
    print("3. Or manually configure using the template file")
    print("4. After configuring, test by triggering motion detection")
    print("=" * 60)
