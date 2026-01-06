#!/usr/bin/env python3
"""
Verification script to check that all Finding model columns exist in the database.
This helps prevent schema mismatch errors.
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text, inspect
from app.core.database import engine
from app.models.finding import Finding

def get_model_columns():
    """Get all column names from the Finding SQLAlchemy model"""
    mapper = inspect(Finding)
    return [column.key for column in mapper.columns]

def get_database_columns():
    """Get all column names from the findings table in the database"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'findings'
            ORDER BY column_name
        """))
        return [row[0] for row in result.fetchall()]

def verify_schema():
    """Verify that all model columns exist in the database"""
    print("=" * 80)
    print("FINDINGS TABLE SCHEMA VERIFICATION")
    print("=" * 80)
    
    model_columns = set(get_model_columns())
    db_columns = set(get_database_columns())
    
    print(f"\nModel columns ({len(model_columns)}):")
    for col in sorted(model_columns):
        print(f"  - {col}")
    
    print(f"\nDatabase columns ({len(db_columns)}):")
    for col in sorted(db_columns):
        print(f"  - {col}")
    
    missing_in_db = model_columns - db_columns
    extra_in_db = db_columns - model_columns
    
    print("\n" + "=" * 80)
    if missing_in_db:
        print(f"❌ MISSING COLUMNS IN DATABASE ({len(missing_in_db)}):")
        for col in sorted(missing_in_db):
            print(f"  - {col}")
        print("\n⚠️  Run 'alembic upgrade head' to add missing columns.")
        return False
    else:
        print("✅ All model columns exist in database!")
    
    if extra_in_db:
        print(f"\n⚠️  EXTRA COLUMNS IN DATABASE (not in model) ({len(extra_in_db)}):")
        for col in sorted(extra_in_db):
            print(f"  - {col}")
        print("(These are usually fine - may be legacy columns)")
    
    print("=" * 80)
    return len(missing_in_db) == 0

if __name__ == '__main__':
    try:
        success = verify_schema()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error during verification: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

