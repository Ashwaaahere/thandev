"""create notifications table

Revision ID: 0013_create_notifications_table
Revises: 0012_add_tool_result_id_to_findings
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0013_create_notifications_table'
down_revision = '0012_add_tool_result_id_to_findings'
branch_labels = None
depends_on = None


def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    is_postgresql = bind.dialect.name == 'postgresql'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create notifications table if it doesn't exist
    if 'notifications' not in existing_tables:
        # Check if tenants and users tables exist (they may be created later by migration 0020)
        tenants_exists = 'tenants' in existing_tables
        users_exists = 'users' in existing_tables
        
        # Create table columns first (without foreign keys if referenced tables don't exist)
        table_args = []
        if tenants_exists and users_exists:
            # Both tables exist, we can create foreign keys
            table_args = [
                sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_notifications_tenant_id'),
                sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_notifications_owner_id'),
            ]
        
        op.create_table('notifications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tenant_id', sa.String(36), nullable=False),
            sa.Column('owner_id', sa.String(36), nullable=False),
            sa.Column('type', sa.String(50), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('message', sa.Text, nullable=True),
            sa.Column('link_url', sa.String(512), nullable=True),
            sa.Column('is_read', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
            *table_args
        )
        
        # Add foreign keys separately if tables exist (for PostgreSQL)
        # This allows the table to be created even if referenced tables don't exist yet
        if is_postgresql and tenants_exists and users_exists:
            # Foreign keys are already in table_args, so this is handled above
            pass
        elif is_postgresql and (tenants_exists or users_exists):
            # Add FKs individually if only one exists (edge case)
            if tenants_exists:
                op.create_foreign_key('fk_notifications_tenant_id', 'notifications', 'tenants', ['tenant_id'], ['id'])
            if users_exists:
                op.create_foreign_key('fk_notifications_owner_id', 'notifications', 'users', ['owner_id'], ['id'])
        
        # Create indexes
        op.create_index('ix_notifications_tenant_id', 'notifications', ['tenant_id'])
        op.create_index('ix_notifications_owner_id', 'notifications', ['owner_id'])
        op.create_index('ix_notifications_type', 'notifications', ['type'])
        op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
        op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
        
        # Create composite index for efficient queries
        op.create_index(
            'idx_notifications_tenant_owner_read_created',
            'notifications',
            ['tenant_id', 'owner_id', 'is_read', 'created_at']
        )


def downgrade():
    # Drop indexes first
    op.drop_index('idx_notifications_tenant_owner_read_created', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_owner_id', table_name='notifications')
    op.drop_index('ix_notifications_tenant_id', table_name='notifications')
    
    # Drop table
    op.drop_table('notifications')

