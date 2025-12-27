"""add_project_id_to_scan_jobs

Add project_id column to scan_jobs table to match the current model schema.
This migration is idempotent and handles both fresh and existing databases.

Revision ID: 0021_add_project_id_to_scan_jobs
Revises: 0020_create_core_tables_users_tenants_projects
Create Date: 2025-12-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '0021_add_project_id_to_scan_jobs'
down_revision = '0020_create_core_tables_users_tenants_projects'
branch_labels = None
depends_on = None


def table_exists(table_name: str, inspector) -> bool:
    """Check if a table exists"""
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str, inspector) -> bool:
    """Check if a column exists in a table"""
    if not table_exists(table_name, inspector):
        return False
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)


def upgrade():
    """Add project_id column to scan_jobs table if it doesn't exist"""
    bind = op.get_bind()
    inspector = inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # Only proceed if scan_jobs table exists
    if not table_exists('scan_jobs', inspector):
        logger.info("scan_jobs table does not exist, skipping project_id addition")
        return
    
    # Check if project_id column already exists
    if column_exists('scan_jobs', 'project_id', inspector):
        logger.info("project_id column already exists in scan_jobs table, skipping")
        return
    
    logger.info("Adding project_id column to scan_jobs table...")
    
    # Projects table should exist by this migration (created by 0014b or 0020)
    if not table_exists('projects', inspector):
        logger.warning("projects table does not exist, adding project_id as nullable for now")
        op.add_column('scan_jobs', sa.Column('project_id', sa.String(36), nullable=True))
    else:
        # Add project_id column with foreign key constraint
        # For fresh DB with no scan_jobs data, we can make it non-nullable
        # Since this migration runs after projects table is created, and scan_jobs
        # would have been created in migration 0002 (old schema), we're migrating the schema.
        # For fresh DBs, there should be no data, so non-nullable is safe.
        op.add_column('scan_jobs', sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False))
        
        # Create index on project_id
        if is_postgresql:
            op.execute("CREATE INDEX IF NOT EXISTS ix_scan_jobs_project_id ON scan_jobs (project_id)")
        else:
            try:
                op.create_index('ix_scan_jobs_project_id', 'scan_jobs', ['project_id'])
            except Exception:
                pass  # Index may already exist
    
    logger.info("✓ Added project_id column to scan_jobs table")


def downgrade():
    """Remove project_id column from scan_jobs table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if not table_exists('scan_jobs', inspector):
        return
    
    if not column_exists('scan_jobs', 'project_id', inspector):
        return
    
    # Drop index first
    try:
        op.drop_index('ix_scan_jobs_project_id', table_name='scan_jobs')
    except Exception:
        pass  # Index may not exist
    
    # Drop column
    op.drop_column('scan_jobs', 'project_id')

