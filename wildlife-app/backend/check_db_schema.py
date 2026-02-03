
from sqlalchemy import create_engine, inspect, text
from config import DATABASE_URL
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_schema():
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    tables = inspector.get_table_names(schema='public') # PostGreSQL schema
    print(f"Tables: {tables}")
    
    if 'detections' in tables:
        columns = inspector.get_columns('detections')
        print("\nColumns in 'detections' table:")
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")

if __name__ == "__main__":
    check_schema()
