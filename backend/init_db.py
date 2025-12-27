import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base
from sqlalchemy import create_engine
import logging

# Import all models to ensure they're registered with Base
# New model structure
from app.models import (
    User, Tenant, Project, ScanJob, Finding, ToolResult,
    DomainVerification, DomainVerificationStatus, Entitlement,
    PerformanceScan, Notification, AuditLog, AllowedDomain
)

# Import legacy models from old models.py file
try:
    from app.models import ThreatItem, PerformanceScanJob
except ImportError:
    # Try importing from the old models.py file directly
    try:
        import app.models as legacy_models
        ThreatItem = getattr(legacy_models, 'ThreatItem', None)
        PerformanceScanJob = getattr(legacy_models, 'PerformanceScanJob', None)
    except (ImportError, AttributeError):
        pass

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
    logger.info('All model tables have been created.')
else:
    logger.error('DATABASE_URL not found!')
    sys.exit(1)

