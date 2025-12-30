"""add tier default to scan_jobs

Revision ID: 0026_add_tier_default
Revises: 0025_fix_scanlevel_enum
Create Date: 2025-12-30 05:00:00.000000

This migration ensures scan_jobs.tier has a DEFAULT of 'basic' to prevent
NotNullViolation errors when tier is not explicitly set. Also backfills any
existing NULL values.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0026_add_tier_default'
down_revision = '0025_fix_scanlevel_enum'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add DEFAULT 'basic' to scan_jobs.tier column and backfill any NULL values.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping tier default (SQLite doesn't support ALTER COLUMN SET DEFAULT easily)")
        # For SQLite, we'll rely on the server_default in the model
        return
    
    # Check if tier column exists
    column_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs' 
            AND column_name = 'tier'
        )
    """)).scalar()
    
    if not column_exists:
        print("tier column does not exist in scan_jobs, skipping default addition")
        return
    
    # Check current default
    current_default = conn.execute(text("""
        SELECT column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'scan_jobs'
        AND column_name = 'tier'
    """)).scalar()
    
    print(f"Current tier default: {current_default}")
    
    # Set DEFAULT 'basic' if not already set
    if current_default != "'basic'":
        try:
            conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN tier SET DEFAULT 'basic'"))
            conn.commit()
            print("Set tier default to 'basic'")
        except Exception as e:
            print(f"Warning: Could not set tier default: {e}")
            conn.rollback()
    else:
        print("tier default already set to 'basic'")
    
    # Backfill any existing NULL values
    try:
        result = conn.execute(text("""
            UPDATE scan_jobs 
            SET tier = 'basic' 
            WHERE tier IS NULL
        """))
        rows_updated = result.rowcount
        conn.commit()
        if rows_updated > 0:
            print(f"Backfilled {rows_updated} rows with tier='basic'")
        else:
            print("No NULL tier values to backfill")
    except Exception as e:
        print(f"Warning: Could not backfill NULL tier values: {e}")
        conn.rollback()
    
    print("Completed tier default migration")


def downgrade():
    """
    Remove DEFAULT from tier column.
    Note: This does not change existing values, only removes the default.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping tier default removal (SQLite)")
        return
    
    try:
        conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN tier DROP DEFAULT"))
        conn.commit()
        print("Removed tier default")
    except Exception as e:
        print(f"Warning: Could not remove tier default: {e}")
        conn.rollback()

