"""add brain_session_id to scan_jobs

Revision ID: 0006_add_brain_session_id
Revises: 0005_add_ai_plan_fields
Create Date: 2025-12-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_add_brain_session_id'
down_revision = '0005_add_ai_plan_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Add brain_session_id column (String(36), nullable=True, indexed)
    try:
        op.add_column('scan_jobs', 
            sa.Column('brain_session_id', sa.String(36), nullable=True)
        )
        
        # Create index for brain_session_id
        if is_sqlite:
            # SQLite index creation
            op.create_index(
                'ix_scan_jobs_brain_session_id',
                'scan_jobs',
                ['brain_session_id']
            )
        else:
            # PostgreSQL index creation
            op.create_index(
                'ix_scan_jobs_brain_session_id',
                'scan_jobs',
                ['brain_session_id']
            )
    except Exception as e:
        if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
            raise

def downgrade():
    # Drop index first
    try:
        op.drop_index('ix_scan_jobs_brain_session_id', table_name='scan_jobs')
    except Exception as e:
        if 'no such index' not in str(e).lower() and 'does not exist' not in str(e).lower():
            raise
    
    # Remove brain_session_id column
    try:
        op.drop_column('scan_jobs', 'brain_session_id')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise









