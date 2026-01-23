"""add project_urls table

Revision ID: 0035_add_project_urls_table
Revises: 0034_add_dependency_scanning_tables
Create Date: 2026-01-23

This migration creates the project_urls table to support multiple URLs per project.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

# revision identifiers, used by Alembic.
revision = '0035_add_project_urls_table'
down_revision = '0034_add_dependency_scanning_tables'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade():
    """Create project_urls table idempotently."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'project_urls' not in existing_tables:
        logger.info("Creating project_urls table...")
        op.create_table(
            'project_urls',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('url', sa.String(2048), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index('idx_project_urls_project_id', 'project_urls', ['project_id'])
        logger.info("✓ Created project_urls table")
    else:
        logger.info("project_urls table already exists, skipping")


def downgrade():
    """Drop project_urls table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'project_urls' in existing_tables:
        logger.info("Dropping project_urls table...")
        op.drop_index('idx_project_urls_project_id', table_name='project_urls')
        op.drop_table('project_urls')
        logger.info("✓ Dropped project_urls table")
    else:
        logger.info("project_urls table does not exist, skipping")

