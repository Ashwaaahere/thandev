"""fix schema idempotent

Revision ID: 0019_fix_schema_idempotent
Revises: 0018_allowed_domains
Create Date: 2025-01-27

This migration ensures critical indexes and constraints exist, making the schema idempotent.
It safely handles cases where tables/indexes/constraints may already exist.
"""
from alembic import op
import sqlalchemy as sa
import logging

# revision identifiers, used by Alembic.
revision = '0019_fix_schema_idempotent'
down_revision = '0018_allowed_domains'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade():
    """Ensure critical indexes and constraints exist idempotently."""
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    
    if is_postgresql:
        # PostgreSQL-specific idempotent operations
        
        # 1. Ensure idx_threat_item_cve_id index exists
        # Check if threat_item table exists first
        result = bind.execute(sa.text(
            "SELECT to_regclass('public.threat_item')"
        )).scalar()
        
        if result is not None:
            logger.info("threat_item table exists, ensuring idx_threat_item_cve_id index...")
            op.execute(
                "CREATE INDEX IF NOT EXISTS idx_threat_item_cve_id ON threat_item (cve_id)"
            )
            logger.info("✓ idx_threat_item_cve_id index ensured")
        else:
            logger.warning("threat_item table does not exist, skipping index creation")
        
        # 2. Ensure check_status constraint exists on scan_jobs
        # Check if scan_jobs table exists first
        result = bind.execute(sa.text(
            "SELECT to_regclass('public.scan_jobs')"
        )).scalar()
        
        if result is not None:
            logger.info("scan_jobs table exists, ensuring check_status constraint...")
            # Use DO block to check if constraint exists before creating
            op.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'check_status' 
                        AND conrelid = 'scan_jobs'::regclass
                    ) THEN
                        ALTER TABLE scan_jobs 
                        ADD CONSTRAINT check_status 
                        CHECK (status IN ('pending', 'running', 'completed', 'error'));
                    END IF;
                END $$;
            """)
            logger.info("✓ check_status constraint ensured")
        else:
            logger.warning("scan_jobs table does not exist, skipping constraint creation")
    else:
        # SQLite and other databases
        logger.info("Non-PostgreSQL database detected, using SQLite-compatible checks")
        
        inspector = sa.inspect(bind)
        existing_tables = inspector.get_table_names()
        
        # 1. Ensure idx_threat_item_cve_id index exists
        if 'threat_item' in existing_tables:
            logger.info("threat_item table exists, ensuring idx_threat_item_cve_id index...")
            try:
                indexes = inspector.get_indexes('threat_item')
                index_exists = any(idx['name'] == 'idx_threat_item_cve_id' for idx in indexes)
                
                if not index_exists:
                    op.create_index('idx_threat_item_cve_id', 'threat_item', ['cve_id'])
                    logger.info("✓ idx_threat_item_cve_id index created")
                else:
                    logger.info("✓ idx_threat_item_cve_id index already exists")
            except Exception as e:
                logger.warning(f"Could not check/create idx_threat_item_cve_id: {e}")
        else:
            logger.warning("threat_item table does not exist, skipping index creation")
        
        # 2. For SQLite, constraints are in CREATE TABLE, so we skip constraint creation
        # (SQLite doesn't support adding CHECK constraints via ALTER TABLE)
        if 'scan_jobs' in existing_tables:
            logger.info("scan_jobs table exists (SQLite constraints are in table definition)")
        else:
            logger.warning("scan_jobs table does not exist")


def downgrade():
    """Downgrade is a no-op for this idempotent fix migration."""
    # This migration only ensures things exist, so downgrade does nothing
    # The actual indexes/constraints will be dropped by their original migrations
    pass

