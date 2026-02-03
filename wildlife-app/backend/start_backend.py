#!/usr/bin/env python3
"""Simple script to start the backend server with better error handling"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """Check if required dependencies are available"""
    missing = []
    
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")
    
    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")
    
    try:
        import sqlalchemy
    except ImportError:
        missing.append("sqlalchemy")
    
    if missing:
        print(f"ERROR: Missing required dependencies: {', '.join(missing)}")
        print("Please install them with: pip install -r requirements.txt")
        return False
    
    return True

def check_database():
    """Check if database is accessible"""
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Database connection successful")
        return True
    except Exception as e:
        print(f"[WARN] Database connection failed: {e}")
        print("[INFO] Backend will start but database features may not work")
        return False

def main():
    """Main entry point"""
    print("=" * 60)
    print("Wildlife Backend Server Startup")
    print("=" * 60)
    
    # Check dependencies
    print("\n[1] Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("[OK] All dependencies available")
    
    # Check database
    print("\n[2] Checking database connection...")
    check_database()
    
    # Start server
    print("\n[3] Starting backend server...")
    print("=" * 60)
    print("Backend will be available at: http://localhost:8001")
    print("API Documentation at: http://localhost:8001/docs")
    print("Health Check at: http://localhost:8001/health")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        import uvicorn
        from main import app
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            reload=False,  # Disable reload for production
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n[INFO] Server stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

