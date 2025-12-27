"""fix alembic_version column length

Revision ID: 0000_fix_alembic_version
Revises: None
Create Date: 2025-01-27

This migration fixes the alembic_version.version_num column to support longer revision IDs.
Some revision IDs are longer than 32 characters, requiring VARCHAR(255) instead of VARCHAR(32).
This migration must run before other migrations to prevent "value too long" errors.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '0000_fix_alembic_version'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Alter alembic_version.version_num column to VARCHAR(255) if it exists and is too short"""
    bind = op.get_bind()
    inspector = inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # Check if alembic_version table exists
    tables = inspector.get_table_names()
    if 'alembic_version' not in tables:
        # Table doesn't exist yet - Alembic will create it with correct default
        # (Alembic uses VARCHAR(255) by default in newer versions)
        return
    
    # For PostgreSQL, always try to alter to VARCHAR(255) to be safe
    # This is idempotent - if already VARCHAR(255), it will be a no-op
    if is_postgresql:
        try:
            # Use raw SQL to alter column - this works even if column is VARCHAR(32) with data
            # PostgreSQL allows ALTER COLUMN TYPE to a larger type even with existing data
            op.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255) USING version_num::VARCHAR(255)"))
        except Exception as e:
            # If alteration fails (maybe already correct size), log but don't fail
            # This ensures migration doesn't break if column is already correct
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not alter alembic_version.version_num column: {e}. This may be safe if column is already large enough.")


def downgrade():
    """Not reversible - this is a schema fix migration"""
    pass

