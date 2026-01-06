"""Database diagnostic utilities for production introspection (verification ONLY)

This file must NOT run automatically on app startup.
It should be runnable with:
    python -c 'from app.db.diagnostics import inspect_scan_jobs_constraints; inspect_scan_jobs_constraints()'
"""
from sqlalchemy import text
from app.core.database import engine


def inspect_scan_jobs_constraints():
    """
    Introspect scan_jobs table constraints and current values.
    Prints current alembic_version, constraint defs for scan_jobs (check_tier, check_status),
    and distinct tier and status values.
    """
    with engine.connect() as conn:
        # Check if PostgreSQL
        is_postgresql = conn.dialect.name == 'postgresql'
        
        if not is_postgresql:
            print("Not PostgreSQL, skipping constraint inspection")
            return
        
        # Get Alembic version
        try:
            alembic_version = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
            print(f"Alembic version: {alembic_version}")
        except Exception as e:
            print(f"Alembic version: ERROR - {e}")
        
        # Get check_tier constraint definition
        try:
            tier_constraint = conn.execute(text("""
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_tier'
            """)).scalar()
            if tier_constraint:
                print(f"check_tier constraint: {tier_constraint}")
            else:
                print("check_tier constraint: NOT FOUND")
        except Exception as e:
            print(f"check_tier constraint: ERROR - {e}")
        
        # Get check_status constraint definition
        try:
            status_constraint = conn.execute(text("""
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_status'
            """)).scalar()
            if status_constraint:
                print(f"check_status constraint: {status_constraint}")
            else:
                print("check_status constraint: NOT FOUND")
        except Exception as e:
            print(f"check_status constraint: ERROR - {e}")
        
        # Get distinct tier values
        try:
            tier_values = conn.execute(text("SELECT DISTINCT tier FROM scan_jobs ORDER BY tier")).fetchall()
            tier_list = [row[0] for row in tier_values]
            print(f"Distinct tier values: {tier_list}")
        except Exception as e:
            print(f"Distinct tier values: ERROR - {e}")
        
        # Get distinct status values
        try:
            status_values = conn.execute(text("SELECT DISTINCT status FROM scan_jobs ORDER BY status")).fetchall()
            status_list = [row[0] for row in status_values]
            print(f"Distinct status values: {status_list}")
        except Exception as e:
            print(f"Distinct status values: ERROR - {e}")


if __name__ == '__main__':
    inspect_scan_jobs_constraints()

