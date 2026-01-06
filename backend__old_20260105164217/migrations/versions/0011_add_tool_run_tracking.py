"""add tool run tracking fields to tool_results

Revision ID: 0011_add_tool_run_tracking
Revises: 0010_add_ai_enrichment_fields
Create Date: 2025-12-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0011_add_tool_run_tracking'
down_revision = '0010_add_ai_enrichment_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Add output_path column (path to output file)
    op.add_column('tool_results', 
        sa.Column('output_path', sa.String(512), nullable=True)
    )
    
    # Add stdout_preview column (first 1000 chars of stdout)
    op.add_column('tool_results', 
        sa.Column('stdout_preview', sa.Text(), nullable=True)
    )
    
    # Add stderr_preview column (first 1000 chars of stderr)
    op.add_column('tool_results', 
        sa.Column('stderr_preview', sa.Text(), nullable=True)
    )
    
    # Add parsed_findings_count column
    op.add_column('tool_results', 
        sa.Column('parsed_findings_count', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Add created_findings_count column
    op.add_column('tool_results', 
        sa.Column('created_findings_count', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Add meta JSON column (for tool args, version, command details)
    if is_sqlite:
        # SQLite uses TEXT for JSON
        op.add_column('tool_results', 
            sa.Column('meta', sa.Text(), nullable=True)
        )
    else:
        # PostgreSQL uses JSON type
        op.add_column('tool_results', 
            sa.Column('meta', sa.JSON(), nullable=True)
        )
    
    # Add duration_ms column (duration in milliseconds)
    op.add_column('tool_results', 
        sa.Column('duration_ms', sa.Integer(), nullable=True)
    )
    
    # Create index on output_path for faster lookups
    try:
        op.create_index('ix_tool_results_output_path', 'tool_results', ['output_path'])
    except Exception:
        # Index might already exist, ignore
        pass


def downgrade():
    # Drop index
    try:
        op.drop_index('ix_tool_results_output_path', 'tool_results')
    except Exception:
        pass
    
    # Drop columns
    op.drop_column('tool_results', 'duration_ms')
    op.drop_column('tool_results', 'meta')
    op.drop_column('tool_results', 'created_findings_count')
    op.drop_column('tool_results', 'parsed_findings_count')
    op.drop_column('tool_results', 'stderr_preview')
    op.drop_column('tool_results', 'stdout_preview')
    op.drop_column('tool_results', 'output_path')

