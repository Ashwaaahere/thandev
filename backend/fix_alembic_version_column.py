#!/usr/bin/env python3
"""
Fix alembic_version.version_num column length to support longer revision IDs.

This script should run BEFORE alembic upgrade head to ensure the column can store
revision IDs longer than 32 characters.
"""
import sys
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings


def fix_alembic_version_column():
    """Alter alembic_version.version_num column to VARCHAR(255) if needed"""
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    
    try:
        with engine.begin() as conn:
            inspector = inspect(engine)
            
            # Check if alembic_version table exists
            tables = inspector.get_table_names()
            if 'alembic_version' not in tables:
                print("alembic_version table does not exist yet - Alembic will create it with correct size")
                return
            
            # Check current column definition
            columns = inspector.get_columns('alembic_version')
            version_num_col = next((col for col in columns if col['name'] == 'version_num'), None)
            
            if not version_num_col:
                print("version_num column does not exist - Alembic will create it")
                return
            
            # Get the column type as string
            col_type = str(version_num_col['type'])
            
            # Check if we need to alter it (for PostgreSQL)
            if settings.DATABASE_URL.startswith('postgresql'):
                # Always try to alter to VARCHAR(255) - PostgreSQL allows this even with data
                # Using USING clause to ensure safe conversion
                print(f"Current column type: {col_type}")
                print("Altering alembic_version.version_num to VARCHAR(255)...")
                try:
                    # Use USING clause for safe conversion - works even if column already has data
                    conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255) USING version_num::VARCHAR(255)"))
                    print("✓ Successfully altered column to VARCHAR(255)")
                except Exception as e:
                    error_str = str(e).lower()
                    # If column is already VARCHAR(255) or larger, PostgreSQL might error or succeed silently
                    # Check if error suggests it's already correct
                    if 'already' in error_str or 'duplicate' in error_str or 'does not exist' in error_str:
                        print(f"Column may already be correct size: {col_type}")
                    else:
                        print(f"Warning: Could not alter column: {e}")
                        # Don't fail - let migration handle it if needed
            else:
                # SQLite - VARCHAR has no length limit
                print(f"Using SQLite - no column length limit needed (current type: {col_type})")
                
    except OperationalError as e:
        # If we can't alter, log but don't fail (maybe table is locked or doesn't exist)
        print(f"Warning: Could not alter alembic_version column: {e}")
        print("This is usually safe - Alembic will handle it if needed")
    except Exception as e:
        print(f"Error fixing alembic_version column: {e}")
        # Don't fail hard - let Alembic handle it
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    fix_alembic_version_column()

