"""add AI enrichment fields to findings

Revision ID: 0010_add_ai_enrichment_fields
Revises: 0009_add_tool_status_tracking
Create Date: 2025-12-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0010_add_ai_enrichment_fields'
down_revision = '0009_add_tool_status_tracking'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Add AI enrichment fields
    try:
        op.add_column('findings', 
            sa.Column('impact_summary', sa.Text(), nullable=True)
        )
        op.add_column('findings', 
            sa.Column('ai_source', sa.String(50), nullable=True)
        )
        op.add_column('findings', 
            sa.Column('ai_model', sa.String(100), nullable=True)
        )
        op.add_column('findings', 
            sa.Column('ai_confidence', sa.Float(), nullable=True)
        )
        op.add_column('findings', 
            sa.Column('ai_last_updated_at', sa.DateTime(timezone=True), nullable=True)
        )
    except Exception as e:
        if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
            raise

def downgrade():
    # Drop AI enrichment fields
    try:
        op.drop_column('findings', 'ai_last_updated_at')
        op.drop_column('findings', 'ai_confidence')
        op.drop_column('findings', 'ai_model')
        op.drop_column('findings', 'ai_source')
        op.drop_column('findings', 'impact_summary')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise




