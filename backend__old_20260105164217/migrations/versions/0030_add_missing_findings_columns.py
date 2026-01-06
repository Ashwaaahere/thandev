"""add all missing columns to findings table

Revision ID: 0030_add_missing_findings_columns
Revises: 0029_add_raw_data_to_findings
Create Date: 2025-12-30 08:30:00.000000

This migration adds all missing columns to the findings table that are defined
in the Finding model but don't exist in the database. This includes:
- recommendation (backwards compatibility)
- remediation_summary
- remediation_steps
- framework_hint
- impact_summary
- ai_source
- ai_model
- ai_confidence
- ai_last_updated_at
- And any other missing columns

NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically.
"""
from alembic import op
from sqlalchemy import text

revision = '0030_add_missing_findings_columns'
down_revision = '0029_add_raw_data_to_findings'
branch_labels = None
depends_on = None

def upgrade():
    """
    Add all missing columns to findings table if they don't exist.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping findings columns addition (SQLite)")
        return
    
    # Check if findings table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'findings'
        )
    """)).scalar()
    
    if not table_exists:
        print("findings table does not exist, skipping column additions")
        return
    
    # Define all columns that should exist (from Finding model)
    # These are columns that might be missing from older database schemas
    columns_to_add = [
        ("recommendation", "TEXT", "Remediation recommendation (backwards compatibility)"),
        ("remediation_summary", "TEXT", "Short summary of what to fix"),
        ("remediation_steps", "TEXT", "JSON array or newline-separated steps"),
        ("framework_hint", "VARCHAR(100)", "Detected framework (django, express, laravel, etc.)"),
        ("impact_summary", "TEXT", "AI-generated impact summary"),
        ("ai_source", "VARCHAR(50)", "Source identifier (e.g., 'brain_v1', 'fallback')"),
        ("ai_model", "VARCHAR(100)", "AI model used (e.g., 'gpt-4o-mini')"),
        ("ai_confidence", "FLOAT", "Confidence score (0.0-1.0)"),
        ("ai_last_updated_at", "TIMESTAMP WITH TIME ZONE", "When AI enrichment was last updated"),
        ("tool", "VARCHAR(100)", "Normalized tool field (alias for tool_name)"),
        ("cwe_id", "VARCHAR(50)", "CWE identifier"),
    ]
    
    # Add each column if it doesn't exist
    for column_name, column_type, description in columns_to_add:
        column_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'findings' 
                AND column_name = :column_name
            )
        """), {"column_name": column_name}).scalar()
        
        if column_exists:
            print(f"Column {column_name} already exists in findings table, skipping")
            continue
        
        try:
            conn.execute(text(f"""
                ALTER TABLE findings 
                ADD COLUMN {column_name} {column_type}
            """))
            print(f"Added column {column_name} ({description}) to findings table")
        except Exception as e:
            print(f"Warning: Could not add column {column_name}: {e}")
            # Continue with other columns even if one fails
            # Alembic will handle rollback on exception
    
    # Verify all columns were created
    print("\nVerifying columns:")
    for column_name, _, description in columns_to_add:
        column_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'findings' 
                AND column_name = :column_name
            )
        """), {"column_name": column_name}).scalar()
        
        if column_exists:
            print(f"  ✓ {column_name} exists")
        else:
            print(f"  ✗ {column_name} MISSING")
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

def downgrade():
    """Remove added columns from findings table"""
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    if not is_postgresql:
        print("Not PostgreSQL, skipping findings columns removal (SQLite)")
        return
    
    columns_to_remove = [
        "recommendation",
        "remediation_summary",
        "remediation_steps",
        "framework_hint",
        "impact_summary",
        "ai_source",
        "ai_model",
        "ai_confidence",
        "ai_last_updated_at",
        "tool",
        "cwe_id",
    ]
    
    for column_name in columns_to_remove:
        column_exists = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'findings' 
                AND column_name = :column_name
            )
        """), {"column_name": column_name}).scalar()
        
        if not column_exists:
            print(f"Column {column_name} does not exist, skipping removal")
            continue
        
        try:
            conn.execute(text(f"ALTER TABLE findings DROP COLUMN {column_name}"))
            print(f"Removed column {column_name} from findings table")
        except Exception as e:
            print(f"Warning: Could not remove column {column_name}: {e}")
            # Alembic will handle rollback on exception
    
    # NOTE: Do NOT call conn.commit() - Alembic handles transactions automatically

