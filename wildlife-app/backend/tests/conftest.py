"""Pytest configuration and fixtures"""
import pytest
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing config
os.environ["ENVIRONMENT"] = "test"
os.environ["DB_NAME"] = "wildlife_test"
os.environ["DB_SCHEMA"] = "test"
os.environ["DB_USER"] = "postgres"
os.environ["DB_PASSWORD"] = "postgres"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"

from database import Base, get_db
from config import DATABASE_URL, DB_SCHEMA


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine"""
    # Use in-memory SQLite for fast tests, or PostgreSQL for integration tests
    test_db_url = os.getenv("TEST_DATABASE_URL", DATABASE_URL)
    
    if "sqlite" in test_db_url.lower():
        engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    else:
        engine = create_engine(test_db_url)
    
    # Create schema if needed
    if DB_SCHEMA and DB_SCHEMA != "public":
        with engine.connect() as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}")
            conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    if DB_SCHEMA and DB_SCHEMA != "public":
        with engine.connect() as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {DB_SCHEMA} CASCADE")
            conn.commit()
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a database session for each test"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    # Rollback transaction and close
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client"""
    from fastapi.testclient import TestClient
    from main import app
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_camera_data():
    """Sample camera data for testing"""
    return {
        "id": 1,
        "name": "Test Camera",
        "url": "http://test-camera.local",
        "is_active": True,
        "width": 1280,
        "height": 720,
        "framerate": 30
    }


@pytest.fixture
def sample_detection_data():
    """Sample detection data for testing"""
    return {
        "camera_id": 1,
        "species": "Deer",
        "confidence": 0.85,
        "image_path": "/test/path/image.jpg",
        "timestamp": "2024-01-01T12:00:00"
    }
