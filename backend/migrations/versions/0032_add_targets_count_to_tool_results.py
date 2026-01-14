"""add targets_count to tool_results

Revision ID: 0032_add_targets_count_to_tool_results
Revises: 0031_add_tool_run_id_unique_constraint
Create Date: 2026-01-12 10:00:00.000000

This migration adds targets_count column to tool_results table.
This field tracks how many targets (URLs/params/requests) were fed to the tool.

NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically.
"""
from alembic import op
from sqlalchemy import text
import sqlalchemy as sa

revision = '0032_add_targets_count_to_tool_results'
down_revision = '0031_add_tool_run_id_unique_constraint'
branch_labels = None
depends_on = None

def upgrade():
    """
    Add targets_count column to tool_results.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    is_sqlite = conn.dialect.name == 'sqlite'
    
    if is_sqlite:
        print("SQLite detected - adding targets_count column")
        try:
            op.add_column('tool_results', 
                sa.Column('targets_count', sa.Integer(), nullable=False, server_default='0')
            )
            print("Added targets_count column to tool_results table")
        except Exception as e:
            # Column might already exist
            print(f"targets_count column may already exist: {e}")
        return
    
    if not is_postgresql:
        print(f"Unsupported database: {conn.dialect.name}, skipping targets_count addition")
        return
    
    # Check if tool_results table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'tool_results'
        )
    """)).scalar()
    
    if not table_exists:
        print("tool_results table does not exist, skipping targets_count addition")
        return
    
    # Check if targets_count column already exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'tool_results' 
            AND column_name = 'targets_count'
        )
    """)).scalar()
    
    if not column_exists:
        # Add targets_count column with default 0
        op.add_column('tool_results', 
            sa.Column('targets_count', sa.Integer(), nullable=False, server_default='0')
        )
        print("Added targets_count column to tool_results table")
    else:
        print("targets_count column already exists, skipping")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

def downgrade():
    """Remove targets_count column"""
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    is_sqlite = conn.dialect.name == 'sqlite'
    
    if is_sqlite:
        try:
            op.drop_column('tool_results', 'targets_count')
            print("Dropped targets_count column from tool_results table")
        except Exception as e:
            print(f"Warning: Could not drop targets_count column: {e}")
        return
    
    if not is_postgresql:
        print(f"Unsupported database: {conn.dialect.name}, skipping targets_count removal")
        return
    
    # Drop column
    try:
        op.drop_column('tool_results', 'targets_count')
        print("Dropped targets_count column from tool_results table")
    except Exception as e:
        print(f"Warning: Could not drop targets_count column: {e}")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically
