import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Base, ThreatItem, ScanJob, PerformanceScanJob
from sqlalchemy import create_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    logger.info(f'Creating database tables using: {DATABASE_URL[:20]}...')
    engine = create_engine(DATABASE_URL)
    
    # Create all tables defined in models
    Base.metadata.create_all(engine)
    logger.info('Database tables created successfully!')
    logger.info('Tables created: threat_item, scan_jobs, performance_scan_jobs')
else:
    logger.error('DATABASE_URL not found!')
    sys.exit(1)

