import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base
from sqlalchemy import create_engine
import logging

# Import all models to ensure they're registered with Base
# New model structure (from app/models/ directory)
from app.models import (
    User, Tenant, Project, ScanJob, Finding, ToolResult,
    DomainVerification, DomainVerificationStatus, Entitlement,
    PerformanceScan, Notification, AuditLog, AllowedDomain
)

# Import legacy models from old app/models.py file (not the directory)
# These models are still used by some routers
try:
    # Import the old models.py file directly (not the package)
    import importlib.util
    import os
    models_file = os.path.join(os.path.dirname(__file__), 'app', 'models.py')
    if os.path.exists(models_file):
        spec = importlib.util.spec_from_file_location("app_models_legacy", models_file)
        legacy_models = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_models)
        # Access the models from the loaded module
        ThreatItem = getattr(legacy_models, 'ThreatItem', None)
        PerformanceScanJob = getattr(legacy_models, 'PerformanceScanJob', None)
    else:
        ThreatItem = None
        PerformanceScanJob = None
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import legacy models: {e}")
    ThreatItem = None
    PerformanceScanJob = None

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

