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
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create notifications table if it doesn't exist
    if 'notifications' not in existing_tables:
        op.create_table('notifications',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('type', sa.String(50), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('message', sa.Text, nullable=True),
            sa.Column('link_url', sa.String(512), nullable=True),
            sa.Column('is_read', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        )
        
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

