"""comprehensive fix for tier constraint to allow canonical lowercase values

Revision ID: 0028_fix_tier_constraint
Revises: 0027_fix_status_constraint
Create Date: 2025-12-30 07:00:00.000000

This migration fixes the check_tier constraint to allow canonical tier values
('basic', 'pro', 'advanced') that match scan_level enum values.

Steps:
1. Drop existing check_tier constraint
2. Backfill ALL legacy tier values to canonical lowercase values
3. Ensure tier DEFAULT is 'basic' (matches code expectation)
4. Ensure tier is NOT NULL
5. Recreate constraint with canonical values

NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically.
"""
from alembic import op
from sqlalchemy import text

revision = '0028_fix_tier_constraint'
down_revision = '0027_fix_status_constraint'
branch_labels = None
depends_on = None

def upgrade():
    """
    Comprehensive tier constraint fix.
    Handles ALL legacy tier values and ensures canonical lowercase values.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping tier constraint fix")
        return
    
    # Log current constraint definition (for verification)
    try:
        current_constraint = conn.execute(text("""
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_tier'
        """)).scalar()
        print(f"BEFORE: check_tier = {current_constraint}")
    except Exception:
        print("BEFORE: No existing check_tier constraint found")
    
    # 1. Drop existing constraint
    conn.execute(text("ALTER TABLE scan_jobs DROP CONSTRAINT IF EXISTS check_tier"))
    print("Dropped existing check_tier constraint")
    
    # 2. Backfill ALL legacy tier values (comprehensive, case-insensitive)
    # Maps: level0/level1/level2, BASIC/PRO/ADVANCED, free/personal/team/enterprise -> basic/pro/advanced
    result = conn.execute(text("""
        UPDATE scan_jobs 
        SET tier = CASE 
            -- Legacy numeric tiers
            WHEN tier = 'level0' THEN 'basic'
            WHEN tier = 'level1' THEN 'pro'
            WHEN tier = 'level2' THEN 'advanced'
            -- Uppercase enum names
            WHEN UPPER(tier) = 'BASIC' THEN 'basic'
            WHEN UPPER(tier) = 'PRO' THEN 'pro'
            WHEN UPPER(tier) = 'ADVANCED' THEN 'advanced'
            -- Legacy plan names (case-insensitive)
            WHEN LOWER(tier) = 'free' THEN 'basic'
            WHEN LOWER(tier) = 'personal' THEN 'pro'
            WHEN LOWER(tier) = 'team' THEN 'pro'
            WHEN LOWER(tier) = 'enterprise' THEN 'advanced'
            -- Already correct lowercase values
            WHEN tier IN ('basic', 'pro', 'advanced') THEN tier
            -- Safe default for any other values
            ELSE 'basic'
        END
        WHERE tier IS NOT NULL
    """))
    rows_updated = result.rowcount
    print(f"Backfilled {rows_updated} rows with canonical tier values")
    
    # 3. Ensure DEFAULT 'basic' (matches code expectation)
    conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN tier SET DEFAULT 'basic'"))
    print("Set tier DEFAULT to 'basic'")
    
    # 4. Ensure NOT NULL (if not already)
    try:
        conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN tier SET NOT NULL"))
        print("Set tier to NOT NULL")
    except Exception as e:
        print(f"tier already NOT NULL or error: {e}")
    
    # 5. Recreate constraint with canonical lowercase values
    conn.execute(text("""
        ALTER TABLE scan_jobs 
        ADD CONSTRAINT check_tier 
        CHECK (tier IN ('basic', 'pro', 'advanced'))
    """))
    print("Created new check_tier constraint")
    
    # Verify constraint was created correctly
    new_constraint = conn.execute(text("""
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_tier'
    """)).scalar()
    print(f"AFTER: check_tier = {new_constraint}")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

def downgrade():
    """Revert to old constraint (level0/level1/level2)"""
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        return
    
    conn.execute(text("ALTER TABLE scan_jobs DROP CONSTRAINT IF EXISTS check_tier"))
    conn.execute(text("""
        ALTER TABLE scan_jobs 
        ADD CONSTRAINT check_tier 
        CHECK (tier IN ('level0', 'level1', 'level2'))
    """))
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

