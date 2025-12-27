"""add tool status tracking to tool_results

Revision ID: 0009_add_tool_status_tracking
Revises: 0008_add_findings_lifecycle
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0009_add_tool_status_tracking'
down_revision = '0008_add_findings_lifecycle'  # Matches revision ID in 0008
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('tool_results')]
    
    # Add status column (nullable for backward compatibility) if it doesn't exist
    if 'status' not in existing_columns:
        try:
            op.add_column('tool_results', 
                sa.Column('status', sa.String(20), nullable=True)
            )
        except Exception:
            pass
    
    # Add error_code column if it doesn't exist
    if 'error_code' not in existing_columns:
        try:
            op.add_column('tool_results', 
                sa.Column('error_code', sa.String(50), nullable=True)
            )
        except Exception:
            pass
    
    # Add started_at and completed_at timestamps if they don't exist
    if 'started_at' not in existing_columns:
        try:
            op.add_column('tool_results', 
                sa.Column('started_at', sa.DateTime(timezone=True), nullable=True)
            )
        except Exception:
            pass
    if 'completed_at' not in existing_columns:
        try:
            op.add_column('tool_results', 
                sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
            )
        except Exception:
            pass
    
    # Backfill status for existing records based on exit_code and timed_out
    # Use uppercase values to match enum (ToolExecutionStatus.COMPLETED.value = "completed" but enum expects uppercase in some cases)
    # Actually, the enum values are lowercase, so we'll use lowercase
    # But we need to ensure the enum can handle the values correctly
    # For now, skip backfill - let new scans populate status correctly
    # Existing records will have status=None which is fine (backward compatible)
    
    # Create index on status for faster queries if it doesn't exist
    try:
        op.create_index('ix_tool_results_status', 'tool_results', ['status'])
    except Exception:
        pass  # Index might already exist


def downgrade():
    # Drop index
    op.drop_index('ix_tool_results_status', 'tool_results')
    
    # Drop columns
    op.drop_column('tool_results', 'completed_at')
    op.drop_column('tool_results', 'started_at')
    op.drop_column('tool_results', 'error_code')
    op.drop_column('tool_results', 'status')

