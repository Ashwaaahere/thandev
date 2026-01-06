"""create_core_tables_pre_0015

Create tenants, users, and projects tables before migration 0015 needs them.
This ensures that 0015_domain_verification_and_root_domain can safely reference the projects table.

Revision ID: 0014b_create_core_tables_pre_0015
Revises: 0014_add_external_identity_to_users
Create Date: 2025-01-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '0014b_create_core_tables_pre_0015'
down_revision = '0014_add_external_identity_to_users'
branch_labels = None
depends_on = None


def table_exists(table_name: str, inspector) -> bool:
    """Check if a table exists"""
    return table_name in inspector.get_table_names()


def upgrade():
    """Create core tables: tenants, users, projects (idempotent)"""
    bind = op.get_bind()
    inspector = inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    
    # 1. Create tenants table (no dependencies)
    if not table_exists('tenants', inspector):
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
        op.create_index('ix_tenants_name', 'tenants', ['name'])
        logger.info("✓ tenants table created")
    else:
        logger.info("tenants table already exists, skipping")
    
    # 2. Create users table (depends on tenants for FK, but nullable so can be created without data)
    if not table_exists('users', inspector):
        logger.info("Creating users table...")
        table_args = []
        if table_exists('tenants', inspector):
            # Only add FK if tenants exists
            table_args.append(sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_users_tenant_id'))
        
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
            sa.Column('tenant_id', sa.String(36), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            *table_args
        )
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
                pass
        logger.info("✓ users table created")
    else:
        logger.info("users table already exists, skipping")
    
    # 3. Create projects table (depends on users and tenants)
    if not table_exists('projects', inspector):
        logger.info("Creating projects table...")
        table_args = []
        if table_exists('users', inspector):
            table_args.append(sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_projects_owner_id'))
        if table_exists('tenants', inspector):
            table_args.append(sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_projects_tenant_id'))
        
        op.create_table(
            'projects',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('target_url', sa.String(2048), nullable=False),
            sa.Column('root_domain', sa.String(255), nullable=True),
            sa.Column('repo_url', sa.String(2048), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('owner_id', sa.String(36), nullable=False),
            sa.Column('tenant_id', sa.String(36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            *table_args
        )
        op.create_index('ix_projects_name', 'projects', ['name'])
        op.create_index('ix_projects_root_domain', 'projects', ['root_domain'])
        logger.info("✓ projects table created")
    else:
        logger.info("projects table already exists, skipping")


def downgrade():
    """Drop tables in reverse order"""
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if table_exists('projects', inspector):
        op.drop_table('projects')
    if table_exists('users', inspector):
        op.drop_table('users')
    if table_exists('tenants', inspector):
        op.drop_table('tenants')

