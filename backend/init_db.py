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

# Import legacy models from old app/models.py file
# Note: Python will import from app/models/__init__.py first, so we need to
# explicitly import the old models.py file. We'll use a workaround by importing
# the module with a different name to avoid conflicts.
try:
    # Import legacy models by importing the models.py file directly
    # We need to import it in a way that doesn't conflict with the models package
    import sys
    import os
    models_py_path = os.path.join(os.path.dirname(__file__), 'app', 'models.py')
    if os.path.exists(models_py_path):
        # Read and exec the file to load legacy models
        with open(models_py_path, 'r') as f:
            code = f.read()
        # Create a namespace for the legacy models
        legacy_namespace = {'__file__': models_py_path}
        exec(code, legacy_namespace)
        # The models are now in legacy_namespace
        ThreatItem = legacy_namespace.get('ThreatItem')
        PerformanceScanJob = legacy_namespace.get('PerformanceScanJob')
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

