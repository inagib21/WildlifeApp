#!/usr/bin/env python3
"""Clear cache and provide instructions to restart backend"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.caching import clear_cache

print("=" * 60)
print("Clearing All Caches")
print("=" * 60)
print()

# Clear cameras cache
print("Clearing cameras_list cache...")
clear_cache("cameras_list")
print("  [OK] Cleared")

# Clear all caches
print("\nClearing all caches...")
clear_cache()
print("  [OK] All caches cleared")

print()
print("=" * 60)
print("IMPORTANT: Restart the backend server for changes to take effect!")
print("=" * 60)
print()
print("To restart:")
print("  1. Stop the current backend (Ctrl+C in the terminal)")
print("  2. Run: python start_backend.py")
print("  OR use: cd ..\\..\\scripts && control.bat (select option 1)")
print()
