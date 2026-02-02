"""add finding_instances table for deduplicated findings

Revision ID: 0040_add_finding_instances_table
Revises: 0039_add_cascade_to_tool_results_fk
Create Date: 2025-01-13

This migration adds:
1. finding_instances table for storing individual instances of deduplicated findings
2. finding_key and related fields to findings table for improved deduplication
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0040_add_finding_instances_table'
down_revision = '0039_add_cascade_to_tool_results_fk'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add finding_instances table and update findings table with grouping fields.
    """
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Check if columns already exist (for idempotency)
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('findings')] if 'findings' in inspector.get_table_names() else []
    
    # Add new fields to findings table
    if 'finding_key' not in existing_columns:
        op.add_column('findings', sa.Column('finding_key', sa.String(64), nullable=True))
    if 'affected_count' not in existing_columns:
        op.add_column('findings', sa.Column('affected_count', sa.Integer(), nullable=False, server_default='1'))
    if 'rule_family' not in existing_columns:
        op.add_column('findings', sa.Column('rule_family', sa.String(50), nullable=True))
    
    # Create index on finding_key (check if exists first)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('findings')] if 'findings' in inspector.get_table_names() else []
    if 'ix_findings_finding_key' not in existing_indexes:
        op.create_index('ix_findings_finding_key', 'findings', ['finding_key'])
    
    # Create finding_instances table (check if exists first)
    existing_tables = inspector.get_table_names()
    if 'finding_instances' not in existing_tables:
        op.create_table(
            'finding_instances',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('finding_id', sa.String(36), nullable=False),
            sa.Column('url', sa.String(2048), nullable=True),
            sa.Column('path', sa.String(2048), nullable=True),
            sa.Column('http_method', sa.String(10), nullable=True),
            sa.Column('parameter', sa.String(255), nullable=True),
            sa.Column('evidence_snippet', sa.Text(), nullable=True),
            sa.Column('is_static_asset', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
        )
        
        # Create indexes on finding_instances
        op.create_index('ix_finding_instances_finding_id', 'finding_instances', ['finding_id'])
        op.create_index('ix_finding_instances_is_static_asset', 'finding_instances', ['is_static_asset'])


def downgrade():
    """
    Remove finding_instances table and revert findings table changes.
    """
    # Drop finding_instances table (cascades will drop indexes)
    op.drop_table('finding_instances')
    
    # Drop index
    op.drop_index('ix_findings_finding_key', table_name='findings')
    
    # Remove columns from findings table
    op.drop_column('findings', 'rule_family')
    op.drop_column('findings', 'affected_count')
    op.drop_column('findings', 'finding_key')

