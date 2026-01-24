"""add ZAP metadata fields to findings

Revision ID: 0037_add_zap_metadata
Revises: 0036_add_needs_verification
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0037_add_zap_metadata'
down_revision = '0036_add_needs_verification'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'findings' not in existing_tables:
        return
    
    # Check if columns already exist
    columns = [col['name'] for col in inspector.get_columns('findings')]
    
    # Add wasc_id (integer)
    if 'wasc_id' not in columns:
        if is_sqlite:
            op.add_column('findings', sa.Column('wasc_id', sa.Integer(), nullable=True))
        else:
            op.add_column('findings', sa.Column('wasc_id', sa.Integer(), nullable=True))
    
    # Add plugin_id (string)
    if 'plugin_id' not in columns:
        op.add_column('findings', sa.Column('plugin_id', sa.String(50), nullable=True))
    
    # Add alert_ref (string)
    if 'alert_ref' not in columns:
        op.add_column('findings', sa.Column('alert_ref', sa.String(50), nullable=True))
    
    # Add zap_confidence (integer)
    if 'zap_confidence' not in columns:
        if is_sqlite:
            op.add_column('findings', sa.Column('zap_confidence', sa.Integer(), nullable=True))
        else:
            op.add_column('findings', sa.Column('zap_confidence', sa.Integer(), nullable=True))
    
    # Add zap_riskcode (integer)
    if 'zap_riskcode' not in columns:
        if is_sqlite:
            op.add_column('findings', sa.Column('zap_riskcode', sa.Integer(), nullable=True))
        else:
            op.add_column('findings', sa.Column('zap_riskcode', sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'findings' not in existing_tables:
        return
    
    columns = [col['name'] for col in inspector.get_columns('findings')]
    
    if 'wasc_id' in columns:
        op.drop_column('findings', 'wasc_id')
    if 'plugin_id' in columns:
        op.drop_column('findings', 'plugin_id')
    if 'alert_ref' in columns:
        op.drop_column('findings', 'alert_ref')
    if 'zap_confidence' in columns:
        op.drop_column('findings', 'zap_confidence')
    if 'zap_riskcode' in columns:
        op.drop_column('findings', 'zap_riskcode')

