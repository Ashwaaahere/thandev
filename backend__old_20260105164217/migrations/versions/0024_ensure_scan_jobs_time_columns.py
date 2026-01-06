"""ensure scan_jobs has both finished_at and completed_at columns

Revision ID: 0024_ensure_time_columns
Revises: 0023_fix_scan_jobs_columns
Create Date: 2025-12-30 03:00:00.000000

This migration ensures BOTH finished_at and completed_at columns exist in scan_jobs,
and keeps them in sync for backward/forward compatibility.
After this migration, both columns will always be present and synced.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0024_ensure_time_columns'
down_revision = '0023_fix_scan_jobs_columns'
branch_labels = None
depends_on = None


def upgrade():
    """
    Ensure both finished_at and completed_at columns exist and are in sync.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    # Check if table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs'
        )
    """)).scalar()
    
    if not table_exists:
        print("scan_jobs table does not exist, skipping column additions")
        return
    
    # Get existing columns
    existing_columns = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """)).fetchall()
    existing_column_names = {row[0] for row in existing_columns}
    
    # Add finished_at if missing
    if 'finished_at' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN finished_at TIMESTAMP WITH TIME ZONE"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN finished_at DATETIME"))
        print("Added column: finished_at")
    
    # Add completed_at if missing
    if 'completed_at' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN completed_at DATETIME"))
        print("Added column: completed_at")
    
    # Backfill and sync: if one is NULL and the other is NOT NULL, copy the value
    # This ensures both columns have the same value going forward
    if is_postgresql:
        # Sync completed_at from finished_at (for rows where completed_at is NULL but finished_at has a value)
        conn.execute(text("""
            UPDATE scan_jobs 
            SET completed_at = finished_at 
            WHERE completed_at IS NULL AND finished_at IS NOT NULL
        """))
        
        # Sync finished_at from completed_at (for rows where finished_at is NULL but completed_at has a value)
        conn.execute(text("""
            UPDATE scan_jobs 
            SET finished_at = completed_at 
            WHERE finished_at IS NULL AND completed_at IS NOT NULL
        """))
    else:
        # SQLite version
        conn.execute(text("""
            UPDATE scan_jobs 
            SET completed_at = finished_at 
            WHERE completed_at IS NULL AND finished_at IS NOT NULL
        """))
        
        conn.execute(text("""
            UPDATE scan_jobs 
            SET finished_at = completed_at 
            WHERE finished_at IS NULL AND completed_at IS NOT NULL
        """))
    
    conn.commit()
    print("Synced finished_at and completed_at columns")


def downgrade():
    """
    Conservative downgrade: only remove completed_at if it was added by this migration.
    Keep finished_at as it's the original column name.
    """
    conn = op.get_bind()
    
    # Check if table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs'
        )
    """)).scalar()
    
    if not table_exists:
        return
    
    # Get existing columns
    existing_columns = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """)).fetchall()
    existing_column_names = {row[0] for row in existing_columns}
    
    # Only drop completed_at, keep finished_at (original column)
    if 'completed_at' in existing_column_names:
        conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN IF EXISTS completed_at"))
        print("Dropped column: completed_at")
    
    conn.commit()

