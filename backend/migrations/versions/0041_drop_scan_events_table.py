"""drop scan_events table

Revision ID: 0041
Revises: 0040
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0041'
down_revision = '0040_add_finding_instances_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop scan_events table as event log feature is removed"""
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_scan_events_scan_phase")
    op.execute("DROP INDEX IF EXISTS idx_scan_events_scan_tool")
    op.execute("DROP INDEX IF EXISTS idx_scan_events_created_at")
    
    # Drop the table
    op.drop_table('scan_events')


def downgrade() -> None:
    """Recreate scan_events table if needed"""
    # Note: This is a destructive change, downgrade will recreate empty table
    op.create_table('scan_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scan_id', sa.String(length=36), nullable=False),
        sa.Column('phase', sa.String(length=50), nullable=False),
        sa.Column('tool', sa.String(length=50), nullable=True),
        sa.Column('stage', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scan_events_scan_phase', 'scan_events', ['scan_id', 'phase'])
    op.create_index('idx_scan_events_scan_tool', 'scan_events', ['scan_id', 'tool'])
    op.create_index('idx_scan_events_created_at', 'scan_events', ['created_at'])
    op.create_index(op.f('ix_scan_events_scan_id'), 'scan_events', ['scan_id'])









