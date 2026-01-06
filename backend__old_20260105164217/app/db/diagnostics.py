"""Database diagnostic utilities for production introspection"""
from sqlalchemy import text
from app.core.database import engine
import json

def inspect_scan_jobs_constraints():
    """
    Introspect scan_jobs table constraints and current values.
    Returns and prints exact constraint definitions.
    """
    with engine.connect() as conn:
        # Get all constraints
        constraints = conn.execute(text("""
            SELECT conname, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint 
            WHERE conrelid = 'scan_jobs'::regclass
        """)).fetchall()
        
        # Get Alembic version
        alembic_version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        
        # Get distinct tier values
        tier_values = conn.execute(text("SELECT DISTINCT tier FROM scan_jobs ORDER BY tier")).fetchall()
        
        # Get distinct status values
        status_values = conn.execute(text("SELECT DISTINCT status FROM scan_jobs ORDER BY status")).fetchall()
        
        result = {
            'alembic_version': alembic_version,
            'constraints': {row[0]: row[1] for row in constraints},
            'tier_values': [row[0] for row in tier_values],
            'status_values': [row[0] for row in status_values]
        }
        
        print("=" * 80)
        print("PRODUCTION DB INSPECTION RESULTS")
        print("=" * 80)
        print(json.dumps(result, indent=2))
        print("=" * 80)
        return result

if __name__ == '__main__':
    inspect_scan_jobs_constraints()

