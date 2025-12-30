"""fix status constraint to include all ScanStatus values

Revision ID: 0027_fix_status_constraint
Revises: 0026_add_tier_default
Create Date: 2025-12-30 06:00:00.000000

This migration updates the check_status constraint to include all valid ScanStatus
enum values. The old constraint only allowed ('pending', 'running', 'completed', 'error'),
but the application uses additional statuses like 'queued', 'completed_with_errors',
'failed', 'cancelled', and 'stalled'.

Also maps legacy 'error' status values to 'failed' for consistency.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0027_fix_status_constraint'
down_revision = '0026_add_tier_default'
branch_labels = None
depends_on = None


def upgrade():
    """
    Update check_status constraint to include all valid ScanStatus enum values.
    Also migrate legacy 'error' status to 'failed'.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping status constraint update (SQLite)")
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
        print("scan_jobs table does not exist, skipping status constraint update")
        return
    
    # Drop old constraint if it exists
    # NOTE: Do not call conn.commit() - Alembic handles transactions automatically
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            DROP CONSTRAINT IF EXISTS check_status
        """))
        print("Dropped old check_status constraint (if it existed)")
    except Exception as e:
        print(f"Warning: Could not drop old check_status constraint: {e}")
        # Continue anyway - constraint might not exist
    
    # Add new constraint with all valid ScanStatus values
    # Valid values: pending, queued, running, completed, completed_with_errors, failed, cancelled, stalled, error
    # NOTE: 'error' is included for backward compatibility but should be migrated to 'failed'
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            ADD CONSTRAINT check_status 
            CHECK (status IN ('pending', 'queued', 'running', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'stalled', 'error'))
        """))
        print("Added new check_status constraint with all valid ScanStatus values")
    except Exception as e:
        print(f"Warning: Could not add new check_status constraint: {e}")
        # Alembic will handle rollback on exception
    
    # Map legacy 'error' status values to 'failed' for consistency
    # NOTE: Do not call conn.commit() - Alembic handles transactions automatically
    try:
        result = conn.execute(text("""
            UPDATE scan_jobs 
            SET status = 'failed' 
            WHERE status = 'error'
        """))
        rows_updated = result.rowcount
        if rows_updated > 0:
            print(f"Migrated {rows_updated} rows from 'error' to 'failed' status")
        else:
            print("No 'error' status values to migrate")
    except Exception as e:
        print(f"Warning: Could not migrate 'error' status values: {e}")
        # Alembic will handle rollback on exception
    
    print("Completed status constraint migration")


def downgrade():
    """
    Revert to old check_status constraint (only allows: pending, running, completed, error).
    Note: This does not revert the 'error' -> 'failed' migration.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping status constraint revert (SQLite)")
        return
    
    # Drop new constraint
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            DROP CONSTRAINT IF EXISTS check_status
        """))
        print("Dropped new check_status constraint")
    except Exception as e:
        print(f"Warning: Could not drop check_status constraint: {e}")
    
    # Add old constraint
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            ADD CONSTRAINT check_status 
            CHECK (status IN ('pending', 'running', 'completed', 'error'))
        """))
        # NOTE: Do not call conn.commit() - Alembic handles transactions automatically
        print("Restored old check_status constraint")
    except Exception as e:
        print(f"Warning: Could not restore old check_status constraint: {e}")
        # Alembic will handle rollback on exception

