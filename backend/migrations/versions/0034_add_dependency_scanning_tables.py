"""add dependency scanning tables

Revision ID: 0034_add_dependency_scanning_tables
Revises: 0033_increase_scan_jobs_status_size
Create Date: 2026-01-27

This migration creates tables for dependency scanning:
- scan_artifacts: Stores URL-SCA and Repo-SCA scan results
- integrations: Stores GitHub App and OAuth integrations
- repo_connections: Links repositories to projects
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text
import logging

# revision identifiers, used by Alembic.
revision = '0034_add_dependency_scanning_tables'
down_revision = '0033_increase_scan_jobs_status_size'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade():
    """Create dependency scanning tables idempotently."""
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # Use JSONB for PostgreSQL, JSON for SQLite
    if is_postgresql:
        json_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        json_type = sa.JSON()
    
    # 1. Create scan_artifacts table
    try:
        op.create_table(
            'scan_artifacts',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scan_id', sa.String(36), sa.ForeignKey('scan_jobs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.Text(), nullable=False),  # 'url_sca' or 'repo_sca'
            sa.Column('payload', json_type, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Index('idx_scan_artifacts_scan_id', 'scan_id'),
            sa.Index('idx_scan_artifacts_type', 'type'),
        )
        logger.info("✓ Created scan_artifacts table")
    except Exception as e:
        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
            logger.warning(f"Could not create scan_artifacts table: {e}")
            raise
        logger.info("✓ scan_artifacts table already exists")
    
    # 2. Create integrations table
    try:
        op.create_table(
            'integrations',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('provider', sa.Text(), nullable=False),  # 'github'
            sa.Column('installation_id', sa.Text(), nullable=True),  # GitHub App installation ID
            sa.Column('access_meta', json_type, nullable=False, server_default='{}'),
            sa.Column('token_encrypted', sa.Text(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Index('idx_integrations_user_provider', 'user_id', 'provider'),
        )
        logger.info("✓ Created integrations table")
    except Exception as e:
        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
            logger.warning(f"Could not create integrations table: {e}")
            raise
        logger.info("✓ integrations table already exists")
    
    # 3. Create repo_connections table
    try:
        op.create_table(
            'repo_connections',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.Text(), nullable=False),  # 'github'
            sa.Column('provider_repo_id', sa.Text(), nullable=False),  # GitHub repo ID
            sa.Column('full_name', sa.Text(), nullable=False),  # 'org/repo'
            sa.Column('default_branch', sa.Text(), nullable=True),
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint('project_id', 'provider', 'provider_repo_id', name='uq_repo_connection_project_provider_repo'),
            sa.Index('idx_repo_connections_project_id', 'project_id'),
        )
        logger.info("✓ Created repo_connections table")
    except Exception as e:
        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
            logger.warning(f"Could not create repo_connections table: {e}")
            raise
        logger.info("✓ repo_connections table already exists")


def downgrade():
    """Drop dependency scanning tables."""
    bind = op.get_bind()
    
    # Drop tables in reverse order (respecting foreign keys)
    try:
        op.drop_table('repo_connections')
        logger.info("✓ Dropped repo_connections table")
    except Exception as e:
        logger.warning(f"Could not drop repo_connections table: {e}")
    
    try:
        op.drop_table('integrations')
        logger.info("✓ Dropped integrations table")
    except Exception as e:
        logger.warning(f"Could not drop integrations table: {e}")
    
    try:
        op.drop_table('scan_artifacts')
        logger.info("✓ Dropped scan_artifacts table")
    except Exception as e:
        logger.warning(f"Could not drop scan_artifacts table: {e}")
