#!/usr/bin/env python3
"""Setup test database schema"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DB_NAME"] = "wildlife_test"
os.environ["DB_SCHEMA"] = "test"

from sqlalchemy import create_engine, text
from config import DATABASE_URL, DB_SCHEMA, DB_NAME
from database import Base, create_schema_if_not_exists

def setup_test_database():
    """Create test database schema and tables"""
    print(f"Setting up test database...")
    print(f"Database: {DB_NAME}")
    print(f"Schema: {DB_SCHEMA}")
    print(f"URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    
    try:
        # Create schema
        if DB_SCHEMA and DB_SCHEMA != "public":
            create_schema_if_not_exists(DB_SCHEMA)
            print(f"✓ Created schema: {DB_SCHEMA}")
        
        # Create tables
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        print("✓ Created all tables")
        
        # Verify
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{DB_SCHEMA}'"))
            table_count = result.fetchone()[0]
            print(f"✓ Verified: {table_count} tables in schema {DB_SCHEMA}")
        
        print("\n✅ Test database setup complete!")
        
    except Exception as e:
        print(f"\n❌ Error setting up test database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_test_database()
