"""Add audit_logs table

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006_add_brain_session_id'  # Fix: reference actual revision ID from 0006
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table with improved error handling"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Check if table already exists
        from sqlalchemy import inspect
        bind = op.get_bind()
        inspector = inspect(bind)
        if 'audit_logs' in inspector.get_table_names():
            logger.warning("audit_logs table already exists, skipping creation")
            return
        
        # Create audit_logs table
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=True, index=True),
            sa.Column('tenant_id', sa.String(36), nullable=True, index=True),
            sa.Column('action_type', sa.String(50), nullable=False, index=True),
            sa.Column('target_type', sa.String(50), nullable=True),  # e.g., 'scan', 'project', 'finding'
            sa.Column('target_id', sa.String(36), nullable=True),  # ID of the target (scan_id, project_id, etc.)
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
            sa.Column('event_metadata', sa.JSON, nullable=True),  # Additional context (scan_level, error_message, etc.) - renamed from 'metadata' as it's reserved in SQLAlchemy
            sa.Column('ip_address', sa.String(45), nullable=True),  # IPv4 or IPv6
            sa.Column('user_agent', sa.String(500), nullable=True),
        )
        
        # Create index on (tenant_id, timestamp) for efficient queries
        op.create_index('ix_audit_logs_tenant_timestamp', 'audit_logs', ['tenant_id', 'timestamp'])
        logger.info("Successfully created audit_logs table")
    except Exception as e:
        logger.error(f"Failed to create audit_logs table: {e}", exc_info=True)
        raise RuntimeError(
            f"Migration failed while creating audit_logs table: {str(e)}. "
            f"Please check database permissions and connection."
        ) from e


def downgrade() -> None:
    op.drop_index('ix_audit_logs_tenant_timestamp', table_name='audit_logs')
    op.drop_table('audit_logs')

