#!/usr/bin/env python3
"""Switch between test and production environments"""
import os
import sys
import shutil
from pathlib import Path

def switch_environment(env: str):
    """Switch to the specified environment"""
    if env not in ["test", "production", "development"]:
        print(f"Error: Invalid environment '{env}'. Must be 'test', 'production', or 'development'")
        sys.exit(1)
    
    backend_dir = Path(__file__).parent.parent
    env_file = backend_dir / f".env.{env}"
    current_env = backend_dir / ".env"
    
    if not env_file.exists():
        print(f"Error: Environment file {env_file} does not exist")
        print(f"Please create it from .env.example")
        sys.exit(1)
    
    # Backup current .env if it exists
    if current_env.exists():
        backup_file = backend_dir / ".env.backup"
        shutil.copy2(current_env, backup_file)
        print(f"Backed up current .env to .env.backup")
    
    # Copy environment file to .env
    shutil.copy2(env_file, current_env)
    print(f"Switched to {env} environment")
    print(f"Environment file: {env_file}")
    print(f"\n⚠️  Remember to restart the backend server for changes to take effect")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python switch_env.py <environment>")
        print("Environments: test, production, development")
        sys.exit(1)
    
    switch_environment(sys.argv[1])
