#!/usr/bin/env python3
"""Optimize motion detection settings for better detection rates"""
import os
import re
from pathlib import Path

def optimize_camera_config(config_path: str, camera_id: int):
    """Optimize a camera config file for better detection sensitivity"""
    
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return False
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Current thresholds are 45000-46000 - these are too high
    # Lower threshold = more sensitive (detects smaller motion)
    # Recommended: 30000-35000 for better wildlife detection
    
    # Optimize threshold (lower = more sensitive)
    threshold_match = re.search(r'^threshold\s+(\d+)', content, re.MULTILINE)
    if threshold_match:
        current_threshold = int(threshold_match.group(1))
        # Lower threshold by 30-40% for better sensitivity
        new_threshold = int(current_threshold * 0.65)
        content = re.sub(
            r'^threshold\s+\d+',
            f'threshold {new_threshold}',
            content,
            flags=re.MULTILINE
        )
        print(f"  Threshold: {current_threshold} -> {new_threshold} (more sensitive)")
    
    # Reduce minimum_motion_frames (lower = triggers faster)
    # Current: 4 frames, Recommended: 2-3 frames
    min_frames_match = re.search(r'^minimum_motion_frames\s+(\d+)', content, re.MULTILINE)
    if min_frames_match:
        current_frames = int(min_frames_match.group(1))
        if current_frames > 2:
            new_frames = 2
            content = re.sub(
                r'^minimum_motion_frames\s+\d+',
                f'minimum_motion_frames {new_frames}',
                content,
                flags=re.MULTILINE
            )
            print(f"  Minimum motion frames: {current_frames} -> {new_frames} (faster triggering)")
    
    # Reduce event_gap (lower = detects events closer together)
    # Current: 3 seconds, Recommended: 1-2 seconds
    event_gap_match = re.search(r'^event_gap\s+(\d+)', content, re.MULTILINE)
    if event_gap_match:
        current_gap = int(event_gap_match.group(1))
        if current_gap > 1:
            new_gap = 1
            content = re.sub(
                r'^event_gap\s+\d+',
                f'event_gap {new_gap}',
                content,
                flags=re.MULTILINE
            )
            print(f"  Event gap: {current_gap}s -> {new_gap}s (more frequent detections)")
    
    # Ensure motion detection is enabled
    if 'motion_detection on' not in content:
        # Find the @motion_detection line and ensure it's on
        content = re.sub(
            r'# @motion_detection\s+\w+',
            '# @motion_detection on',
            content
        )
        print(f"  Motion detection: Enabled")
    
    # Ensure picture_output_motion is on
    if 'picture_output_motion on' not in content:
        content = re.sub(
            r'^picture_output_motion\s+\w+',
            'picture_output_motion on',
            content,
            flags=re.MULTILINE
        )
        print(f"  Picture output on motion: Enabled")
    
    if content != original_content:
        # Create backup
        backup_path = config_path + '.backup'
        with open(backup_path, 'w') as f:
            f.write(original_content)
        
        # Write optimized config
        with open(config_path, 'w') as f:
            f.write(content)
        
        return True
    else:
        print(f"  No changes needed")
        return False

def main():
    """Optimize all camera configs"""
    config_dir = Path(__file__).parent.parent / 'motioneye_config'
    
    print("=" * 80)
    print("Optimizing Motion Detection Settings")
    print("=" * 80)
    print("\nThis will:")
    print("  - Lower motion thresholds (more sensitive)")
    print("  - Reduce minimum motion frames (faster triggering)")
    print("  - Reduce event gap (more frequent detections)")
    print("  - Ensure motion detection is enabled")
    print("\nBackups will be created as .backup files\n")
    
    optimized_count = 0
    
    for i in range(1, 9):  # Cameras 1-8
        config_file = config_dir / f'camera-{i}.conf'
        if config_file.exists():
            print(f"\nCamera {i}:")
            if optimize_camera_config(str(config_file), i):
                optimized_count += 1
                print(f"  [OK] Optimized")
            else:
                print(f"  - No changes")
        else:
            print(f"\nCamera {i}: Config file not found")
    
    print(f"\n{'='*80}")
    print(f"Optimization Complete")
    print(f"{'='*80}")
    print(f"Optimized: {optimized_count} camera(s)")
    print(f"\nNext Steps:")
    print(f"  1. Restart MotionEye to apply changes:")
    print(f"     docker restart wildlife-motioneye")
    print(f"  2. Monitor detection rates - should see more detections")
    print(f"  3. If too many false positives, increase thresholds slightly")

if __name__ == "__main__":
    main()

