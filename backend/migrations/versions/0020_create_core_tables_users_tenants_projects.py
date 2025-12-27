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
from sqlalchemy.sql import text
from sqlalchemy.dialects import postgresql
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
    
    # 4. Add root_domain column to projects if missing (migration 0015 may have skipped this)
    if table_exists('projects'):
        project_cols = inspector.get_columns('projects')
        project_col_names = {col['name'] for col in project_cols}
        if 'root_domain' not in project_col_names:
            logger.info("Adding root_domain column to projects table...")
            op.add_column('projects', sa.Column('root_domain', sa.String(255), nullable=True))
            op.create_index('ix_projects_root_domain', 'projects', ['root_domain'])
            logger.info("✓ Added root_domain column to projects")
    
    # 5. Create domain_verifications table if missing (migration 0015 may have skipped this)
    if not table_exists('domain_verifications') and table_exists('tenants') and table_exists('projects'):
        logger.info("Creating domain_verifications table...")
        # Use enum type (should exist from migration 0015)
        # For SQLite, use String instead of ENUM
        if is_postgresql:
            domain_status_enum = postgresql.ENUM(
                "pending", "verified", "failed", "expired",
                name="domain_verification_status",
                create_type=False,
            )
        else:
            # SQLite doesn't support ENUM, use String
            domain_status_enum = sa.String(20)
        
        op.create_table(
            'domain_verifications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
            sa.Column('domain', sa.String(255), nullable=False),
            sa.Column('status', domain_status_enum, nullable=False),
            sa.Column('token', sa.String(255), nullable=False),
            sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index('ix_domain_verifications_project_domain', 'domain_verifications', ['project_id', 'domain'])
        logger.info("✓ domain_verifications table created")
    
    # 6. Create entitlements table if missing (migration 0016 may have skipped this)
    if not table_exists('entitlements') and table_exists('tenants') and table_exists('users'):
        logger.info("Creating entitlements table...")
        # Use JSONB for PostgreSQL, Text for SQLite
        limits_json_type = postgresql.JSON() if is_postgresql else sa.Text()
        
        op.create_table(
            'entitlements',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('plan_name', sa.String(50), nullable=False),
            sa.Column('limits_json', limits_json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
        op.create_index('ix_entitlements_tenant_id', 'entitlements', ['tenant_id'])
        op.create_index('ix_entitlements_user_id', 'entitlements', ['user_id'])
        logger.info("✓ entitlements table created")
    
    # 7. Add foreign keys to notifications table if it exists but doesn't have them
    # This handles the case where notifications table was created before tenants/users
    if table_exists('notifications'):
        logger.info("Checking notifications table foreign keys...")
        # Check if foreign key constraints exist
        notifications_fks = inspector.get_foreign_keys('notifications')
        fk_names = {fk['name'] for fk in notifications_fks}
        
        # Add tenant_id FK if missing and tenants table exists
        if 'fk_notifications_tenant_id' not in fk_names and table_exists('tenants'):
            if is_postgresql:
                op.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'fk_notifications_tenant_id' 
                            AND conrelid = 'notifications'::regclass
                        ) THEN
                            ALTER TABLE notifications
                            ADD CONSTRAINT fk_notifications_tenant_id
                            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
                        END IF;
                    END $$;
                """)
            else:
                try:
                    op.create_foreign_key('fk_notifications_tenant_id', 'notifications', 'tenants', ['tenant_id'], ['id'])
                except Exception:
                    pass  # May already exist
            logger.info("✓ Added tenant_id foreign key to notifications")
        
        # Add owner_id FK if missing and users table exists
        if 'fk_notifications_owner_id' not in fk_names and table_exists('users'):
            if is_postgresql:
                op.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = 'fk_notifications_owner_id' 
                            AND conrelid = 'notifications'::regclass
                        ) THEN
                            ALTER TABLE notifications
                            ADD CONSTRAINT fk_notifications_owner_id
                            FOREIGN KEY (owner_id) REFERENCES users(id);
                        END IF;
                    END $$;
                """)
            else:
                try:
                    op.create_foreign_key('fk_notifications_owner_id', 'notifications', 'users', ['owner_id'], ['id'])
                except Exception:
                    pass  # May already exist
            logger.info("✓ Added owner_id foreign key to notifications")


def downgrade():
    """Drop core tables in reverse order"""
    if table_exists('projects'):
        op.drop_table('projects')
    if table_exists('users'):
        op.drop_table('users')
    if table_exists('tenants'):
        op.drop_table('tenants')

