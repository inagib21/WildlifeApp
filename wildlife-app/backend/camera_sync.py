import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Type

from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


def _map_motioneye_camera(camera_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": camera_data.get("id"),
        "name": camera_data.get("name", f"Camera{camera_data.get('id')}"),
        "url": camera_data.get("device_url", ""),
        "is_active": camera_data.get("enabled", True),
        "width": camera_data.get("width", 1280),
        "height": camera_data.get("height", 720),
        "framerate": camera_data.get("framerate", 30),
        "stream_port": camera_data.get("streaming_port", 8081),
        "stream_quality": camera_data.get("streaming_quality", 100),
        "stream_maxrate": camera_data.get("streaming_framerate", 30),
        "stream_localhost": False,
        "detection_enabled": camera_data.get("motion_detection", True),
        "detection_threshold": camera_data.get("frame_change_threshold", 1500),
        "detection_smart_mask_speed": camera_data.get("smart_mask_sluggishness", 10),
        "movie_output": camera_data.get("movies", True),
        "movie_quality": camera_data.get("movie_quality", 100),
        "movie_codec": camera_data.get("movie_format", "mkv"),
        "snapshot_interval": camera_data.get("snapshot_interval", 0),
        "target_dir": camera_data.get("root_directory", "./motioneye_media"),
    }


def sync_motioneye_cameras(
    db: Session,
    motioneye_client,
    camera_model: Type,
) -> Dict[str, Any]:
    """Synchronise MotionEye camera definitions into the local database."""
    motioneye_cameras: List[Dict[str, Any]] = motioneye_client.get_cameras() or []
    motioneye_ids: Set[int] = set()
    synced_count = 0
    updated_count = 0
    removed_count = 0

    for me_camera in motioneye_cameras:
        mapped = _map_motioneye_camera(me_camera)
        camera_id = mapped.get("id")
        if camera_id is None:
            logger.warning("Skipping MotionEye camera without id: %s", me_camera)
            continue

        motioneye_ids.add(camera_id)

        existing = db.get(camera_model, camera_id)

        if existing is None:
            db_camera = camera_model(**mapped)
            db.add(db_camera)
            synced_count += 1
            logger.info("Synced new MotionEye camera %s (%s)", mapped["name"], camera_id)
        else:
            updated = False
            # Always update is_active from MotionEye to keep it in sync
            me_is_active = mapped.get("is_active", True)
            if existing.is_active != me_is_active:
                existing.is_active = me_is_active
                updated = True
                logger.info("Updated camera %s (%s) is_active: %s -> %s", mapped["name"], camera_id, existing.is_active, me_is_active)
            
            # Update other fields
            for field, value in mapped.items():
                if field != "is_active":  # Already handled above
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        updated = True
            if updated:
                updated_count += 1
                logger.info("Updated MotionEye camera %s (%s) - Active: %s", mapped["name"], camera_id, existing.is_active)

    removed_count = 0
    if motioneye_ids:
        rows = db.query(camera_model.id).all()
        existing_ids = {row[0] for row in rows}
        orphan_ids = existing_ids - motioneye_ids

        for orphan_id in orphan_ids:
            camera = db.get(camera_model, orphan_id)
            if camera:
                db.delete(camera)
                removed_count += 1
                logger.info("Removed stale MotionEye camera %s (%s)", camera.name, orphan_id)

    db.commit()

    return {
        "message": (
            f"Synchronised {synced_count} new cameras, updated {updated_count} existing cameras, "
            f"removed {removed_count} stale cameras."
        ),
        "synced": synced_count,
        "updated": updated_count,
        "removed": removed_count,
        "total_cameras": len(motioneye_cameras),
    }


class CameraSyncService:
    """Background service that polls MotionEye and keeps cameras in sync."""

    def __init__(
        self,
        session_factory: sessionmaker,
        motioneye_client,
        camera_model: Type,
        poll_interval_seconds: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._motioneye_client = motioneye_client
        self._camera_model = camera_model
        self._poll_interval = poll_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task

    async def run_once(self) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_blocking)

    async def _run_loop(self) -> None:
        logger.info("CameraSyncService started with interval %s seconds", self._poll_interval)
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_once()
                except Exception as exc:  # pragma: no cover - safety net
                    logger.error("Camera sync failed: %s", exc, exc_info=True)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            logger.info("CameraSyncService stopped")

    def _sync_blocking(self) -> Dict[str, Any]:
        session = self._session_factory()
        try:
            return sync_motioneye_cameras(session, self._motioneye_client, self._camera_model)
        finally:
            session.close()

