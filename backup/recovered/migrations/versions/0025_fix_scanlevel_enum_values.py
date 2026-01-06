"""fix scanlevel enum values to use lowercase canonical values

Revision ID: 0025_fix_scanlevel_enum
Revises: 0024_ensure_time_columns
Create Date: 2025-12-30 04:00:00.000000

This migration ensures the scanlevel enum has lowercase canonical values
(basic, pro, advanced) and backfills any existing rows that use uppercase variants.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0025_fix_scanlevel_enum'
down_revision = '0024_ensure_time_columns'
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix scanlevel enum to use lowercase canonical values: basic, pro, advanced.
    This is idempotent and safe to run multiple times.
    
    CRITICAL: This migration must run on the SAME DATABASE_URL used by runtime.
    Fly.io release_command ensures migrations run before containers start.
    """
    import os
    from urllib.parse import urlparse
    
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    # Log database connection info (redact password) for verification
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            parsed = urlparse(db_url)
            db_display = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port or 'default'}{parsed.path}"
            print(f"Migration running on database: {db_display}")
        except Exception:
            print(f"Migration running on database: {db_url.split('@')[-1] if '@' in db_url else 'configured'}")
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping enum fix (SQLite doesn't use enums)")
        return
    
    # Check if enum type exists
    enum_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM pg_type WHERE typname = 'scanlevel'
        )
    """)).scalar()
    
    if not enum_exists:
        # Create enum with canonical lowercase values
        conn.execute(text("CREATE TYPE scanlevel AS ENUM ('basic', 'pro', 'advanced')"))
        print("Created scanlevel enum with values: basic, pro, advanced")
    else:
        # Enum exists - add missing canonical values if they don't exist
        # Note: Postgres doesn't support IF NOT EXISTS for ADD VALUE, so we check first
        existing_values = conn.execute(text("""
            SELECT enumlabel 
            FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = 'scanlevel'
            ORDER BY enumsortorder
        """)).fetchall()
        existing_value_set = {row[0] for row in existing_values}
        
        print(f"Existing scanlevel enum values: {sorted(existing_value_set)}")
        
        # Add missing canonical lowercase values
        canonical_values = {'basic', 'pro', 'advanced'}
        missing_values = canonical_values - existing_value_set
        
        for value in missing_values:
            try:
                # Postgres doesn't support IF NOT EXISTS, so we use a DO block to check
                conn.execute(text(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_enum 
                            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
                            WHERE pg_type.typname = 'scanlevel' 
                            AND enumlabel = '{value}'
                        ) THEN
                            ALTER TYPE scanlevel ADD VALUE '{value}';
                        END IF;
                    END $$;
                """))
                print(f"Added enum value: {value}")
            except Exception as e:
                # If value already exists (race condition or already added), that's fine
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"Enum value {value} already exists, skipping")
                else:
                    print(f"Warning: Could not add enum value {value}: {e}")
        
        # Backfill existing rows that use uppercase variants
        # First, check what values actually exist in the table
        distinct_values = conn.execute(text("""
            SELECT DISTINCT scan_level::text 
            FROM scan_jobs 
            WHERE scan_level IS NOT NULL
        """)).fetchall()
        distinct_value_set = {row[0] for row in distinct_values}
        
        print(f"Distinct scan_level values in scan_jobs: {sorted(distinct_value_set)}")
        
        # Map uppercase variants to lowercase canonical values
        value_mapping = {
            'BASIC': 'basic',
            'PRO': 'pro',
            'ADVANCED': 'advanced',
            'Basic': 'basic',
            'Pro': 'pro',
            'Advanced': 'advanced',
        }
        
        # Update rows that have uppercase variants
        for old_value, new_value in value_mapping.items():
            if old_value in distinct_value_set and new_value in existing_value_set:
                try:
                    # Use a safe update that only affects rows with the old value
                    # We need to cast to text for comparison since we can't directly compare enum values
                    rows_updated = conn.execute(text(f"""
                        UPDATE scan_jobs 
                        SET scan_level = '{new_value}'::scanlevel
                        WHERE scan_level::text = '{old_value}'
                    """))
                    if rows_updated.rowcount > 0:
                        print(f"Updated {rows_updated.rowcount} rows from {old_value} to {new_value}")
                except Exception as e:
                    # If the old value doesn't exist as an enum value, that's fine
                    if 'invalid input value' in str(e).lower() or 'does not exist' in str(e).lower():
                        print(f"Value {old_value} not found in enum, skipping update")
                    else:
                        print(f"Warning: Could not update {old_value} to {new_value}: {e}")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically
    print("Completed scanlevel enum fix")


def downgrade():
    """
    Conservative downgrade: no-op.
    We don't remove enum values as Postgres doesn't support removing enum values easily.
    """
    print("Downgrade: no-op (Postgres enum values cannot be easily removed)")

