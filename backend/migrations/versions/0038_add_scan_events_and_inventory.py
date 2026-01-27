"""add scan events and inventory tables

Revision ID: 0038_add_scan_events
Revises: 0037_add_zap_metadata
Create Date: 2026-01-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0038_add_scan_events'
down_revision = '0037_add_zap_metadata'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    is_postgresql = bind.dialect.name == 'postgresql'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Use JSONB for PostgreSQL, JSON for SQLite
    json_type = postgresql.JSONB() if is_postgresql else sa.JSON()
    
    # Create scan_events table
    if 'scan_events' not in existing_tables:
        op.create_table(
            'scan_events',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scan_id', sa.String(36), sa.ForeignKey('scan_jobs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('phase', sa.String(50), nullable=False),
            sa.Column('tool', sa.String(50), nullable=True),
            sa.Column('stage', sa.String(100), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('progress', sa.Float(), nullable=True),
            sa.Column('meta', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        
        # Create indexes
        op.create_index('idx_scan_events_scan_id', 'scan_events', ['scan_id'])
        op.create_index('idx_scan_events_phase', 'scan_events', ['phase'])
        op.create_index('idx_scan_events_tool', 'scan_events', ['tool'])
        op.create_index('idx_scan_events_scan_phase', 'scan_events', ['scan_id', 'phase'])
        op.create_index('idx_scan_events_scan_tool', 'scan_events', ['scan_id', 'tool'])
        op.create_index('idx_scan_events_created_at', 'scan_events', ['created_at'])
    
    # Create scan_tool_states table
    if 'scan_tool_states' not in existing_tables:
        op.create_table(
            'scan_tool_states',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scan_id', sa.String(36), sa.ForeignKey('scan_jobs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tool', sa.String(50), nullable=False),
            sa.Column('phase', sa.String(50), nullable=False),
            sa.Column('stage', sa.String(100), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('progress', sa.Float(), nullable=True),
            sa.Column('meta', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        
        # Create unique constraint and indexes
        op.create_index('uq_scan_tool_phase', 'scan_tool_states', ['scan_id', 'tool', 'phase'], unique=True)
        op.create_index('idx_scan_tool_states_scan_id', 'scan_tool_states', ['scan_id'])
        op.create_index('idx_scan_tool_states_updated_at', 'scan_tool_states', ['updated_at'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Drop scan_tool_states table
    if 'scan_tool_states' in existing_tables:
        op.drop_index('idx_scan_tool_states_updated_at', 'scan_tool_states')
        op.drop_index('idx_scan_tool_states_scan_id', 'scan_tool_states')
        op.drop_index('uq_scan_tool_phase', 'scan_tool_states')
        op.drop_table('scan_tool_states')
    
    # Drop scan_events table
    if 'scan_events' in existing_tables:
        op.drop_index('idx_scan_events_created_at', 'scan_events')
        op.drop_index('idx_scan_events_scan_tool', 'scan_events')
        op.drop_index('idx_scan_events_scan_phase', 'scan_events')
        op.drop_index('idx_scan_events_tool', 'scan_events')
        op.drop_index('idx_scan_events_phase', 'scan_events')
        op.drop_index('idx_scan_events_scan_id', 'scan_events')
        op.drop_table('scan_events')

