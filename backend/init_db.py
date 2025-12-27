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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import legacy models from old app/models.py file ONLY if they don't conflict
# Note: We skip legacy models that conflict with new models (like ScanJob)
try:
    import sys
    import os
    models_py_path = os.path.join(os.path.dirname(__file__), 'app', 'models.py')
    if os.path.exists(models_py_path):
        # Check if we need legacy models (ThreatItem is not in new structure)
        # But skip ScanJob and PerformanceScanJob as they conflict
        with open(models_py_path, 'r') as f:
            code = f.read()
        # Create a namespace for the legacy models, but don't import Base again
        legacy_namespace = {
            '__file__': models_py_path,
            'Base': Base,  # Use the same Base instance
            'Column': __import__('sqlalchemy', fromlist=['Column']).Column,
            'Text': __import__('sqlalchemy', fromlist=['Text']).Text,
            'DateTime': __import__('sqlalchemy', fromlist=['DateTime']).DateTime,
            'Boolean': __import__('sqlalchemy', fromlist=['Boolean']).Boolean,
            'Numeric': __import__('sqlalchemy', fromlist=['Numeric']).Numeric,
            'Integer': __import__('sqlalchemy', fromlist=['Integer']).Integer,
            'String': __import__('sqlalchemy', fromlist=['String']).String,
            'Index': __import__('sqlalchemy', fromlist=['Index']).Index,
            'CheckConstraint': __import__('sqlalchemy', fromlist=['CheckConstraint']).CheckConstraint,
            'JSON': __import__('sqlalchemy', fromlist=['JSON']).JSON,
            'JSONB': __import__('sqlalchemy.dialects.postgresql', fromlist=['JSONB']).JSONB,
            'os': os,
        }
        # Only exec the ThreatItem class definition (skip ScanJob and PerformanceScanJob)
        # We'll extract just the ThreatItem class
        lines = code.split('\n')
        threat_item_lines = []
        in_threat_item = False
        for line in lines:
            if 'class ThreatItem' in line:
                in_threat_item = True
            if in_threat_item:
                threat_item_lines.append(line)
                if line.strip().startswith('class ') and 'ThreatItem' not in line:
                    break
        if threat_item_lines:
            threat_item_code = '\n'.join(threat_item_lines)
            exec(threat_item_code, legacy_namespace)
            ThreatItem = legacy_namespace.get('ThreatItem')
        else:
            ThreatItem = None
    else:
        ThreatItem = None
except Exception as e:
    logger.warning(f"Could not import legacy ThreatItem model: {e}")
    ThreatItem = None

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    logger.info(f'Initializing database using: {DATABASE_URL[:20]}...')
    engine = create_engine(DATABASE_URL)
    
    # For production, we should rely on Alembic migrations for schema creation
    # init_db.py is mainly for development/testing
    # Only create tables if they don't exist (Alembic will handle migrations)
    try:
        Base.metadata.create_all(engine, checkfirst=True)
        logger.info('Database tables verified/created successfully!')
    except Exception as e:
        # If there's an error (e.g., enum conflicts), log it but don't fail
        # Alembic migrations will handle the schema properly
        logger.warning(f'Table creation encountered an issue (this is OK if using Alembic): {e}')
        logger.info('Continuing - Alembic migrations will handle schema updates.')
else:
    logger.error('DATABASE_URL not found!')
    sys.exit(1)

