#!/usr/bin/env python3
"""Clear the cameras cache"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.caching import clear_cache

print("Clearing cameras cache...")
clear_cache("cameras_list")
print("Cache cleared!")
