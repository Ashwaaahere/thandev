"""create_core_tables_users_tenants_projects

Revision ID: 0020_create_core_tables_users_tenants_projects
Revises: 0019_fix_schema_idempotent
Create Date: 2025-01-27

This migration creates the core tables: tenants, users, and projects.
It is idempotent and will skip creation if tables already exist.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
import logging

# revision identifiers, used by Alembic.
revision = '0020_create_core_tables_users_tenants_projects'
down_revision = '0019_fix_schema_idempotent'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def table_exists(table_name):
    """Check if a table exists in the database"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    """Create core tables: tenants, users, projects (idempotent)"""
    bind = op.get_bind()
    inspector = inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # 1. Create tenants table (no dependencies)
    if not table_exists('tenants'):
        logger.info("Creating tenants table...")
        op.create_table(
            'tenants',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('plan', sa.String(50), nullable=False, server_default='free'),
            sa.Column('max_projects', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('max_scans_per_month', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('max_concurrent_scans', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        # Create index on name
        op.create_index('ix_tenants_name', 'tenants', ['name'])
        logger.info("✓ tenants table created")
    else:
        logger.info("tenants table already exists, skipping")
    
    # 2. Create users table (depends on tenants)
    if not table_exists('users'):
        logger.info("Creating users table...")
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('username', sa.String(100), nullable=False),
            sa.Column('hashed_password', sa.String(255), nullable=False, server_default=''),
            sa.Column('full_name', sa.String(255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_approved', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('external_provider', sa.String(50), nullable=True),
            sa.Column('external_user_id', sa.String(255), nullable=True),
            sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        # Create indexes
        op.create_index('ix_users_email', 'users', ['email'], unique=True)
        op.create_index('ix_users_username', 'users', ['username'], unique=True)
        op.create_index('ix_users_external_provider', 'users', ['external_provider'])
        op.create_index('ix_users_external_user_id', 'users', ['external_user_id'])
        # Create unique constraint on (external_provider, external_user_id) if not exists
        if is_postgresql:
            op.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'uq_users_external_identity' 
                        AND conrelid = 'users'::regclass
                    ) THEN
                        ALTER TABLE users 
                        ADD CONSTRAINT uq_users_external_identity 
                        UNIQUE (external_provider, external_user_id);
                    END IF;
                END $$;
            """)
        else:
            # SQLite: try to create unique constraint (may fail if already exists)
            try:
                op.create_unique_constraint('uq_users_external_identity', 'users', ['external_provider', 'external_user_id'])
            except Exception:
                pass  # Constraint may already exist
        logger.info("✓ users table created")
    else:
        logger.info("users table already exists, skipping")
    
    # 3. Create projects table (depends on users and tenants)
    if not table_exists('projects'):
        logger.info("Creating projects table...")
        op.create_table(
            'projects',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('target_url', sa.String(2048), nullable=False),
            sa.Column('root_domain', sa.String(255), nullable=True),
            sa.Column('repo_url', sa.String(2048), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        # Create indexes
        op.create_index('ix_projects_name', 'projects', ['name'])
        op.create_index('ix_projects_root_domain', 'projects', ['root_domain'])
        logger.info("✓ projects table created")
    else:
        logger.info("projects table already exists, skipping")


def downgrade():
    """Drop core tables in reverse order"""
    if table_exists('projects'):
        op.drop_table('projects')
    if table_exists('users'):
        op.drop_table('users')
    if table_exists('tenants'):
        op.drop_table('tenants')

