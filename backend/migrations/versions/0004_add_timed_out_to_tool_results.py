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
