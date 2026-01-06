"""add raw_data column to findings table

Revision ID: 0029_add_raw_data_to_findings
Revises: 0028_fix_tier_constraint
Create Date: 2025-12-30 08:00:00.000000

This migration adds the raw_data column to the findings table.
The column stores JSON string of raw finding data and is nullable.

NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically.
"""
from alembic import op
from sqlalchemy import text

revision = '0029_add_raw_data_to_findings'
down_revision = '0028_fix_tier_constraint'
branch_labels = None
depends_on = None

def upgrade():
    """
    Add raw_data column to findings table if it doesn't exist.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping raw_data column addition (SQLite)")
        return
    
    # Check if findings table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'findings'
        )
    """)).scalar()
    
    if not table_exists:
        print("findings table does not exist, skipping raw_data column addition")
        return
    
    # Check if raw_data column already exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'findings' 
            AND column_name = 'raw_data'
        )
    """)).scalar()
    
    if column_exists:
        print("raw_data column already exists in findings table, skipping")
        return
    
    # Add raw_data column as TEXT NULLABLE
    try:
        conn.execute(text("""
            ALTER TABLE findings 
            ADD COLUMN raw_data TEXT
        """))
        print("Added raw_data column to findings table")
    except Exception as e:
        print(f"Warning: Could not add raw_data column: {e}")
        # Alembic will handle rollback on exception
    
    # Verify column was created
    column_exists_after = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'findings' 
            AND column_name = 'raw_data'
        )
    """)).scalar()
    
    if column_exists_after:
        print("Verified: raw_data column exists in findings table")
    else:
        print("Warning: raw_data column was not created successfully")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

def downgrade():
    """Remove raw_data column from findings table"""
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping raw_data column removal (SQLite)")
        return
    
    # Check if column exists before trying to drop it
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'findings' 
            AND column_name = 'raw_data'
        )
    """)).scalar()
    
    if not column_exists:
        print("raw_data column does not exist, skipping removal")
        return
    
    try:
        conn.execute(text("ALTER TABLE findings DROP COLUMN raw_data"))
        print("Removed raw_data column from findings table")
    except Exception as e:
        print(f"Warning: Could not remove raw_data column: {e}")
        # Alembic will handle rollback on exception
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

