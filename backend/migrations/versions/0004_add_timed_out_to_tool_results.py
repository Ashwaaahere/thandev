"""add timed_out to tool_results

Revision ID: 0004_add_timed_out
Revises: 0003_add_indexes
Create Date: 2025-11-30

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_timed_out'
down_revision = '0003_add_indexes'
branch_labels = None
depends_on = None

def upgrade():
    # Add timed_out column to tool_results table
    # Using INTEGER for SQLite compatibility (0=False, 1=True)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create tool_results table if it doesn't exist
    if 'tool_results' not in existing_tables:
        op.create_table('tool_results',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scan_job_id', sa.String(36), sa.ForeignKey('scan_jobs.id'), nullable=False),
            sa.Column('tool_name', sa.String(100), nullable=False),
            sa.Column('tool_version', sa.String(50), nullable=True),
            sa.Column('output', sa.Text, nullable=True),
            sa.Column('exit_code', sa.Integer, nullable=True),
            sa.Column('execution_time', sa.Float, nullable=True),
            sa.Column('command', sa.Text, nullable=True),
            sa.Column('error_message', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        )
        # Create index on scan_job_id
        op.create_index('ix_tool_results_scan_job_id', 'tool_results', ['scan_job_id'])
        op.create_index('ix_tool_results_tool_name', 'tool_results', ['tool_name'])
    
    # Add timed_out column
    try:
        op.add_column('tool_results', 
            sa.Column('timed_out', sa.Integer(), nullable=False, server_default='0')
        )
    except Exception as e:
        # Column might already exist, check the error message
        if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
            raise
        # Column already exists, skip
        pass

def downgrade():
    # Remove timed_out column
    try:
        op.drop_column('tool_results', 'timed_out')
    except Exception as e:
        # Column might not exist, that's okay
        if 'no such column' not in str(e).lower():
            raise
