import logging
from sqlalchemy import text, inspect, Engine

logger = logging.getLogger(__name__)

def check_and_run_migrations(engine: Engine):
    """
    Check and run database migrations to ensure schema is up to date.
    This handles adding columns and indexes idempotently.
    """
    logger.info("Checking for database migrations...")
    
    try:
        insp = inspect(engine)
        
        # 1. Check/Add 'detections' table columns
        detection_columns = {c['name'] for c in insp.get_columns('detections')}
        
        with engine.connect() as conn:
            # Add file_hash (already present in most envs, but good to check)
            if 'file_hash' not in detection_columns:
                conn.execute(text('ALTER TABLE detections ADD COLUMN file_hash VARCHAR'))
                logger.info('[OK] Added file_hash column to detections table')

            # Add audio/video/sensor columns
            columns_to_add = [
                ('audio_path', 'VARCHAR'),
                ('video_path', 'VARCHAR'),
                ('temperature', 'DOUBLE PRECISION'),
                ('humidity', 'DOUBLE PRECISION'),
                ('pressure', 'DOUBLE PRECISION'),
                ('detections_json', 'TEXT')
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in detection_columns:
                    conn.execute(text(f'ALTER TABLE detections ADD COLUMN {col_name} {col_type}'))
                    logger.info(f'[OK] Added {col_name} column to detections table')
            
            conn.commit()

        # 2. Check/Add 'cameras' table columns
        camera_columns = {c['name'] for c in insp.get_columns('cameras')}
        
        with engine.connect() as conn:
            # Location fields
            if 'latitude' not in camera_columns:
                conn.execute(text('ALTER TABLE cameras ADD COLUMN latitude DOUBLE PRECISION'))
                logger.info('[OK] Added latitude column to cameras table')
            if 'longitude' not in camera_columns:
                conn.execute(text('ALTER TABLE cameras ADD COLUMN longitude DOUBLE PRECISION'))
                logger.info('[OK] Added longitude column to cameras table')
            if 'address' not in camera_columns:
                conn.execute(text('ALTER TABLE cameras ADD COLUMN address VARCHAR'))
                logger.info('[OK] Added address column to cameras table')
                
            # Geofence fields
            geofence_cols = [
                ('geofence_enabled', 'BOOLEAN DEFAULT FALSE NOT NULL'),
                ('geofence_type', 'VARCHAR'),
                ('geofence_data', 'TEXT')
            ]
            
            for col_name, col_def in geofence_cols:
                if col_name not in camera_columns:
                    try:
                        conn.execute(text(f'ALTER TABLE cameras ADD COLUMN {col_name} {col_def}'))
                        logger.info(f'[OK] Added {col_name} column to cameras table')
                    except Exception as e:
                        logger.warning(f'Error adding {col_name}: {e}')
                        conn.rollback()
            
            conn.commit()

        # 3. Create Indexes for Performance
        # Only attempt if table exists (it should by now)
        try:
            existing_indexes = {idx['name'] for idx in insp.get_indexes('detections')}
            
            indexes_to_create = [
                ('idx_detection_video_path', 'detections(video_path)', 'video_path IS NOT NULL'),
                ('idx_detection_audio_path', 'detections(audio_path)', 'audio_path IS NOT NULL'),
                ('idx_detection_date_range', 'detections(timestamp DESC, camera_id)', None),
                ('idx_detection_confidence', 'detections(confidence)', None)
            ]
            
            with engine.connect() as conn:
                for idx_name, idx_def, idx_where in indexes_to_create:
                    if idx_name not in existing_indexes:
                        try:
                            where_clause = f" WHERE {idx_where}" if idx_where else ""
                            conn.execute(text(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}{where_clause}'))
                            logger.info(f'[OK] Added index {idx_name}')
                        except Exception as e:
                            logger.warning(f'Error creating index {idx_name}: {e}')
                conn.commit()
                
        except Exception as e:
            logger.warning(f'Index creation warning: {e}')

        # 4. Check/Add 'known_faces' table columns
        try:
            known_faces_columns = {c['name'] for c in insp.get_columns('known_faces')}
            
            with engine.connect() as conn:
                # Add tolerance column for per-face recognition threshold
                if 'tolerance' not in known_faces_columns:
                    try:
                        conn.execute(text('ALTER TABLE known_faces ADD COLUMN tolerance DOUBLE PRECISION DEFAULT 0.6'))
                        logger.info('[OK] Added tolerance column to known_faces table')
                    except Exception as e:
                        logger.warning(f'Error adding tolerance column: {e}')
                        conn.rollback()
                
                conn.commit()
        except Exception as e:
            logger.warning(f'Known faces migration warning: {e}')

        logger.info("[OK] Database migration check completed")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        # Don't raise, allow app to start even if migration fails (best effort)
