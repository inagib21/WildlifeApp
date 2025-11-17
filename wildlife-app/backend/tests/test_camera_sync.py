import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import Base, Camera


class FakeMotionEyeClient:
    def __init__(self, cameras):
        self._cameras = cameras

    def get_cameras(self):
        return self._cameras


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_sync_motioneye_cameras_adds_new_camera(session):
    from backend.camera_sync import sync_motioneye_cameras

    fake_client = FakeMotionEyeClient(
        [
            {
                "id": 42,
                "name": "New MotionEye Camera",
                "device_url": "rtsp://camera42/stream",
                "enabled": True,
                "width": 1920,
                "height": 1080,
                "framerate": 25,
                "streaming_port": 8765,
                "streaming_quality": 95,
                "streaming_framerate": 20,
                "motion_detection": True,
                "frame_change_threshold": 1800,
                "smart_mask_sluggishness": 12,
                "movies": True,
                "movie_quality": 90,
                "movie_format": "mp4",
                "snapshot_interval": 0,
                "root_directory": "./motioneye_media",
            }
        ]
    )

    result = sync_motioneye_cameras(session, fake_client, Camera)

    camera = session.get(Camera, 42)
    assert camera is not None
    assert camera.name == "New MotionEye Camera"
    assert camera.url == "rtsp://camera42/stream"
    assert result["synced"] == 1
    assert result["total_cameras"] == 1


def test_sync_motioneye_cameras_updates_existing_camera(session):
    from backend.camera_sync import sync_motioneye_cameras

    existing = Camera(
        id=7,
        name="Old Name",
        url="rtsp://old",
        is_active=False,
        width=1280,
        height=720,
        framerate=15,
        stream_port=8081,
        stream_quality=80,
        stream_maxrate=15,
        stream_localhost=False,
        detection_enabled=False,
        detection_threshold=1500,
        detection_smart_mask_speed=10,
        movie_output=True,
        movie_quality=80,
        movie_codec="mkv",
        snapshot_interval=0,
        target_dir="./motioneye_media",
    )
    session.add(existing)
    session.commit()

    fake_client = FakeMotionEyeClient(
        [
            {
                "id": 7,
                "name": "Updated Camera Name",
                "device_url": "rtsp://new",
                "enabled": True,
                "width": 1920,
                "height": 1080,
                "framerate": 30,
                "streaming_port": 9090,
                "streaming_quality": 100,
                "streaming_framerate": 30,
                "motion_detection": True,
                "frame_change_threshold": 2000,
                "smart_mask_sluggishness": 5,
                "movies": True,
                "movie_quality": 100,
                "movie_format": "mp4",
                "snapshot_interval": 5,
                "root_directory": "./motioneye_media",
            }
        ]
    )

    result = sync_motioneye_cameras(session, fake_client, Camera)

    updated = session.get(Camera, 7)
    assert updated.name == "Updated Camera Name"
    assert updated.url == "rtsp://new"
    assert updated.is_active is True
    assert updated.width == 1920
    assert updated.height == 1080
    assert updated.framerate == 30
    assert updated.stream_port == 9090
    assert result["synced"] == 0
    assert result["total_cameras"] == 1


def test_sync_motioneye_cameras_removes_orphaned_entries(session):
    from backend.camera_sync import sync_motioneye_cameras

    active = Camera(
        id=5,
        name="Active Camera",
        url="rtsp://active",
        is_active=True,
    )
    orphan = Camera(
        id=9,
        name="Stale Manual Camera",
        url="rtsp://stale",
        is_active=False,
    )
    session.add_all([active, orphan])
    session.commit()

    fake_client = FakeMotionEyeClient(
        [
            {
                "id": 5,
                "name": "Active Camera",
                "device_url": "rtsp://active",
                "enabled": True,
            }
        ]
    )

    result = sync_motioneye_cameras(session, fake_client, Camera)

    assert session.get(Camera, 5) is not None
    assert session.get(Camera, 9) is None
    assert result["removed"] == 1
    assert result["total_cameras"] == 1

