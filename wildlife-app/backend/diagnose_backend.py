#!/usr/bin/env python3
"""
Diagnose why the backend isn't starting.

This script checks common issues that prevent the backend from starting.
"""

import sys
import os
import subprocess
import requests
import time

print("=" * 60)
print("Backend Diagnostic Tool")
print("=" * 60)
print()

# Check 1: Python venv
print("[1] Checking Python virtual environment...")
venv_python = os.path.join("venv", "Scripts", "python.exe")
if os.path.exists(venv_python):
    print(f"  [OK] Python venv found: {venv_python}")
else:
    print(f"  [FAIL] Python venv NOT found: {venv_python}")
    print("  Fix: Run 'python -m venv venv' in backend directory")
    sys.exit(1)

# Check 2: Main file exists
print("\n[2] Checking main.py...")
if os.path.exists("main.py"):
    print("  [OK] main.py found")
else:
    print("  [FAIL] main.py NOT found")
    sys.exit(1)

# Check 3: Port availability
print("\n[3] Checking port 8001...")
try:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if ":8001" in result.stdout:
        print("  [WARN] Port 8001 is in use")
        print("  Fix: Kill the process using port 8001")
        # Try to find the process
        for line in result.stdout.split("\n"):
            if ":8001" in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1]
                    print(f"    Process ID: {pid}")
                    print(f"    Kill with: taskkill /F /PID {pid}")
    else:
        print("  [OK] Port 8001 is available")
except:
    print("  [WARN] Could not check port (netstat not available)")

# Check 4: Dependencies
print("\n[4] Checking critical dependencies...")
try:
    import fastapi
    print(f"  [OK] fastapi: {fastapi.__version__}")
except ImportError:
    print("  [FAIL] fastapi not installed")
    print("  Fix: pip install fastapi")

try:
    import uvicorn
    print(f"  [OK] uvicorn: {uvicorn.__version__}")
except ImportError:
    print("  [FAIL] uvicorn not installed")
    print("  Fix: pip install uvicorn")

try:
    import sqlalchemy
    print(f"  [OK] sqlalchemy: {sqlalchemy.__version__}")
except ImportError:
    print("  [FAIL] sqlalchemy not installed")
    print("  Fix: pip install sqlalchemy")

# Check 5: Database connection
print("\n[5] Checking database connection...")
try:
    from config import DATABASE_URL
    print(f"  [OK] DATABASE_URL configured")
    # Try to connect (non-blocking check)
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  [OK] Database connection successful")
    except Exception as e:
        print(f"  [WARN] Database connection failed: {e}")
        print("  Note: Backend can start without database, but some features won't work")
except Exception as e:
    print(f"  [WARN] Could not check database: {e}")

# Check 6: Try to import main
print("\n[6] Checking if main.py can be imported...")
try:
    # Add current directory to path
    sys.path.insert(0, os.getcwd())
    import main
    print("  [OK] main.py imports successfully")
except Exception as e:
    print(f"  [FAIL] Cannot import main.py: {e}")
    import traceback
    traceback.print_exc()
    print("\n  This is likely why the backend isn't starting!")
    print("  Check the error above and fix the import issues.")

# Check 7: Try to start backend
print("\n[7] Attempting to start backend (5 second test)...")
try:
    # Try to start in background
    process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a bit
    time.sleep(5)
    
    # Check if it's still running
    if process.poll() is None:
        print("  [OK] Backend process started successfully")
        # Check if it's responding
        try:
            response = requests.get("http://localhost:8001/health", timeout=2)
            if response.status_code == 200:
                print("  [OK] Backend is responding to health checks!")
            else:
                print(f"  [WARN] Backend started but health check returned: {response.status_code}")
        except:
            print("  [WARN] Backend started but not responding yet (may need more time)")
        
        # Kill the test process
        process.terminate()
        process.wait(timeout=2)
    else:
        # Process exited - get error
        stdout, stderr = process.communicate()
        print("  [FAIL] Backend process exited immediately")
        if stderr:
            print("\n  Error output:")
            print("  " + "\n  ".join(stderr.split("\n")[-20:]))  # Last 20 lines
        if stdout:
            print("\n  Standard output:")
            print("  " + "\n  ".join(stdout.split("\n")[-20:]))
except Exception as e:
    print(f"  [FAIL] Could not start backend: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 60)
print("Diagnostic Summary")
print("=" * 60)
print("\nIf backend is still not starting:")
print("1. Check the Backend window for error messages")
print("2. Look for Python import errors")
print("3. Check database connection")
print("4. Verify all dependencies are installed: pip install -r requirements.txt")
print("5. Try starting manually:")
print("   cd wildlife-app/backend")
print("   venv\\Scripts\\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001")
print("=" * 60)

