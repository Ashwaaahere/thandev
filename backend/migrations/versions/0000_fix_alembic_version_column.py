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
    
    # Check current column definition
    columns = inspector.get_columns('alembic_version')
    version_num_col = next((col for col in columns if col['name'] == 'version_num'), None)
    
    if not version_num_col:
        # Column doesn't exist - Alembic will create it
        return
    
    # Get the column type
    col_type = str(version_num_col['type'])
    
    # Check if column is too short (VARCHAR(32) or similar)
    # For PostgreSQL, we check if it's character varying(32)
    # For SQLite, VARCHAR has no length limit, so we skip
    if is_postgresql:
        if 'varying(32)' in col_type.lower() or col_type.lower() == 'character varying(32)':
            # Alter column to VARCHAR(255)
            op.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))
        elif 'varying' in col_type.lower() and '255' not in col_type:
            # If it's VARCHAR but not 255, check if it's shorter than 50 (safety check)
            # Extract number if possible, otherwise just alter to 255 to be safe
            op.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"))


def downgrade():
    """Not reversible - this is a schema fix migration"""
    pass

