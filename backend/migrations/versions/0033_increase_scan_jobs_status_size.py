"""increase scan_jobs status column size

Revision ID: 0033_increase_scan_jobs_status_size
Revises: 0032_add_targets_count_to_tool_results
Create Date: 2026-01-14 03:40:00.000000

This migration increases the status column size from VARCHAR(20) to VARCHAR(50)
to accommodate longer status values like 'completed_with_errors' (22 chars).
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0033_increase_scan_jobs_status_size'
down_revision = '0032_add_targets_count_to_tool_results'
branch_labels = None
depends_on = None


def upgrade():
    """
    Increase scan_jobs.status column size from VARCHAR(20) to VARCHAR(50).
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping status column size increase (SQLite)")
        return
    
    # Check if scan_jobs table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs'
        )
    """)).scalar()
    
    if not table_exists:
        print("scan_jobs table does not exist, skipping status column size increase")
        return
    
    # Check current column size
    current_size = conn.execute(text("""
        SELECT character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'scan_jobs'
        AND column_name = 'status'
    """)).scalar()
    
    if current_size is None:
        print("status column not found, skipping")
        return
    
    if current_size >= 50:
        print(f"status column already has size {current_size} >= 50, skipping")
        return
    
    print(f"Current status column size: {current_size}, increasing to 50")
    
    # Increase column size
    try:
        conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN status TYPE VARCHAR(50)"))
        print("Successfully increased scan_jobs.status column size to VARCHAR(50)")
    except Exception as e:
        print(f"Error increasing status column size: {e}")
        raise


def downgrade():
    """
    Revert status column size back to VARCHAR(20).
    WARNING: This may fail if there are rows with status values longer than 20 characters.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping status column size revert (SQLite)")
        return
    
    # Check if any rows have status values longer than 20 characters
    long_statuses = conn.execute(text("""
        SELECT DISTINCT status
        FROM scan_jobs
        WHERE LENGTH(status) > 20
    """)).fetchall()
    
    if long_statuses:
        print(f"WARNING: Cannot downgrade - found {len(long_statuses)} status values longer than 20 characters:")
        for row in long_statuses:
            print(f"  - {row[0]} (length: {len(row[0])})")
        print("Please update these statuses before downgrading")
        return
    
    try:
        conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN status TYPE VARCHAR(20)"))
        print("Successfully reverted scan_jobs.status column size to VARCHAR(20)")
    except Exception as e:
        print(f"Error reverting status column size: {e}")
        raise
