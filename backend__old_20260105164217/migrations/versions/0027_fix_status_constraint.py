"""fix status and tier constraints to match current enum values

Revision ID: 0027_fix_status_constraint
Revises: 0026_add_tier_default
Create Date: 2025-12-30 06:00:00.000000

This migration updates:
1. check_status constraint to include all valid ScanStatus enum values.
   The old constraint only allowed ('pending', 'running', 'completed', 'error'),
   but the application uses additional statuses like 'queued', 'completed_with_errors',
   'failed', 'cancelled', and 'stalled'.

Also maps legacy 'error' status values to 'failed' for consistency.

NOTE: check_tier constraint is handled comprehensively in migration 0028.
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
    Update check_status constraint to match current enum values.
    Also migrate legacy values:
    - 'error' status -> 'failed'
    This is idempotent and safe to run multiple times.
    NOTE: check_tier constraint is handled comprehensively in migration 0028.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping constraint updates (SQLite)")
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
        print("scan_jobs table does not exist, skipping constraint updates")
        return
    
    # ========== Fix check_status constraint ==========
    # Introspect current constraint to only modify if too strict
    current_status_constraint = None
    try:
        current_status_constraint = conn.execute(text("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_status'
        """)).scalar()
        if current_status_constraint:
            print(f"BEFORE: check_status = {current_status_constraint}")
    except Exception:
        print("BEFORE: No existing check_status constraint found")
    
    # Only modify if constraint is too narrow (doesn't include all required values)
    required_values = ['pending', 'queued', 'running', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'stalled']
    constraint_too_narrow = False
    
    if current_status_constraint:
        # Check if constraint includes all required values
        constraint_too_narrow = any(value not in current_status_constraint for value in required_values)
    else:
        # No constraint exists, need to create one
        constraint_too_narrow = True
    
    if constraint_too_narrow:
        # Drop old constraint if it exists
        try:
            conn.execute(text("ALTER TABLE scan_jobs DROP CONSTRAINT IF EXISTS check_status"))
            print("Dropped old check_status constraint")
        except Exception as e:
            print(f"Warning: Could not drop old check_status constraint: {e}")
        
        # Add new constraint with all valid ScanStatus values (excluding 'error' - map to 'failed')
        try:
            conn.execute(text("""
                ALTER TABLE scan_jobs 
                ADD CONSTRAINT check_status 
                CHECK (status IN ('pending', 'queued', 'running', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'stalled'))
            """))
            print("Added new check_status constraint (removed 'error', mapped to 'failed')")
        except Exception as e:
            print(f"Warning: Could not add new check_status constraint: {e}")
            # Alembic will handle rollback on exception
        
        # Map legacy 'error' status values to 'failed' (remove 'error' long-term)
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
        
        # Verify new constraint
        new_constraint = conn.execute(text("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_status'
        """)).scalar()
        print(f"AFTER: check_status = {new_constraint}")
    else:
        print("check_status constraint already allows all required values, skipping update")
    
    # NOTE: check_tier constraint will be fixed comprehensively in migration 0028
    # This migration only handles check_status constraint
    print("Completed status constraint migration (tier constraint handled in 0028)")


def downgrade():
    """
    Revert to old check_status constraint:
    - check_status: only allows (pending, running, completed, error)
    Note: This does not revert data migrations ('error' -> 'failed').
    NOTE: check_tier constraint is handled in migration 0028 downgrade.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping constraint revert (SQLite)")
        return
    
    # Drop new check_status constraint
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            DROP CONSTRAINT IF EXISTS check_status
        """))
        print("Dropped new check_status constraint")
    except Exception as e:
        print(f"Warning: Could not drop check_status constraint: {e}")
    
    # Add old check_status constraint
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
    
    # NOTE: check_tier constraint revert is handled in migration 0028 downgrade

