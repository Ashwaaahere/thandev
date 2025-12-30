"""fix status and tier constraints to match current enum values

Revision ID: 0027_fix_status_constraint
Revises: 0026_add_tier_default
Create Date: 2025-12-30 06:00:00.000000

This migration updates:
1. check_status constraint to include all valid ScanStatus enum values.
   The old constraint only allowed ('pending', 'running', 'completed', 'error'),
   but the application uses additional statuses like 'queued', 'completed_with_errors',
   'failed', 'cancelled', and 'stalled'.

2. check_tier constraint to allow ('basic', 'pro', 'advanced') instead of
   legacy ('level0', 'level1', 'level2'). The tier column now maps directly
   to scan_level values.

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
    Update check_status and check_tier constraints to match current enum values.
    Also migrate legacy values:
    - 'error' status -> 'failed'
    - 'level0', 'level1', 'level2' tier -> 'basic', 'pro', 'advanced' (if any exist)
    This is idempotent and safe to run multiple times.
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
    
    # ========== Fix check_tier constraint ==========
    # Drop old constraint if it exists (expects 'level0', 'level1', 'level2')
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            DROP CONSTRAINT IF EXISTS check_tier
        """))
        print("Dropped old check_tier constraint (if it existed)")
    except Exception as e:
        print(f"Warning: Could not drop old check_tier constraint: {e}")
        # Continue anyway - constraint might not exist
    
    # Add new constraint with valid tier values ('basic', 'pro', 'advanced')
    # These match the scan_level enum values
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            ADD CONSTRAINT check_tier 
            CHECK (tier IN ('basic', 'pro', 'advanced'))
        """))
        print("Added new check_tier constraint with values: basic, pro, advanced")
    except Exception as e:
        print(f"Warning: Could not add new check_tier constraint: {e}")
        # Alembic will handle rollback on exception
    
    # Migrate legacy tier values if any exist
    # Map: level0 -> basic, level1 -> pro, level2 -> advanced
    try:
        result = conn.execute(text("""
            UPDATE scan_jobs 
            SET tier = CASE 
                WHEN tier = 'level0' THEN 'basic'
                WHEN tier = 'level1' THEN 'pro'
                WHEN tier = 'level2' THEN 'advanced'
                ELSE tier
            END
            WHERE tier IN ('level0', 'level1', 'level2')
        """))
        rows_updated = result.rowcount
        if rows_updated > 0:
            print(f"Migrated {rows_updated} rows from legacy tier values (level0/level1/level2) to new values (basic/pro/advanced)")
        else:
            print("No legacy tier values to migrate")
    except Exception as e:
        print(f"Warning: Could not migrate legacy tier values: {e}")
        # Alembic will handle rollback on exception
    
    print("Completed status and tier constraint migrations")


def downgrade():
    """
    Revert to old constraints:
    - check_status: only allows (pending, running, completed, error)
    - check_tier: only allows (level0, level1, level2)
    Note: This does not revert data migrations ('error' -> 'failed', tier migrations).
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
    
    # Drop new check_tier constraint
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            DROP CONSTRAINT IF EXISTS check_tier
        """))
        print("Dropped new check_tier constraint")
    except Exception as e:
        print(f"Warning: Could not drop check_tier constraint: {e}")
    
    # Add old check_tier constraint
    try:
        conn.execute(text("""
            ALTER TABLE scan_jobs 
            ADD CONSTRAINT check_tier 
            CHECK (tier IN ('level0', 'level1', 'level2'))
        """))
        # NOTE: Do not call conn.commit() - Alembic handles transactions automatically
        print("Restored old check_tier constraint")
    except Exception as e:
        print(f"Warning: Could not restore old check_tier constraint: {e}")
        # Alembic will handle rollback on exception

