"""fix_scan_jobs_missing_columns

Revision ID: 0023_fix_scan_jobs_columns
Revises: 0022_add_scan_jobs_columns
Create Date: 2025-12-30 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0023_fix_scan_jobs_columns'
down_revision = '0022_add_scan_jobs_columns'
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix missing columns in scan_jobs table using raw SQL with IF NOT EXISTS.
    This is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    
    # Check if table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs'
        )
    """)).scalar()
    
    if not table_exists:
        print("scan_jobs table does not exist, skipping column additions")
        return
    
    # Get existing columns
    existing_columns = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """)).fetchall()
    existing_column_names = {row[0] for row in existing_columns}
    
    # Check if PostgreSQL or SQLite
    is_postgresql = conn.dialect.name == 'postgresql'
    
    # Add celery_task_id (String(255), nullable=True, index=True)
    if 'celery_task_id' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN celery_task_id VARCHAR(255)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scan_jobs_celery_task_id ON scan_jobs(celery_task_id)"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN celery_task_id VARCHAR(255)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scan_jobs_celery_task_id ON scan_jobs(celery_task_id)"))
        print("Added column: celery_task_id")
    
    # Add scan_level (Enum for PostgreSQL, String for SQLite)
    if 'scan_level' not in existing_column_names:
        if is_postgresql:
            # Check if enum type exists
            enum_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM pg_type WHERE typname = 'scanlevel'
                )
            """)).scalar()
            
            if not enum_exists:
                conn.execute(text("CREATE TYPE scanlevel AS ENUM ('basic', 'pro', 'advanced')"))
            
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN scan_level scanlevel NOT NULL DEFAULT 'basic'"))
            # Remove default after adding (for idempotency, we'll use DEFAULT in the ALTER)
            conn.execute(text("ALTER TABLE scan_jobs ALTER COLUMN scan_level DROP DEFAULT"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN scan_level VARCHAR(20) NOT NULL DEFAULT 'basic'"))
            # Note: SQLite doesn't support ALTER COLUMN DROP DEFAULT, so we keep the default
        print("Added column: scan_level")
    
    # Add stack_info (JSONB for PostgreSQL, JSON for SQLite)
    if 'stack_info' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN stack_info JSONB"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN stack_info TEXT"))
        print("Added column: stack_info")
    
    # Add error_message (Text, nullable=True)
    if 'error_message' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN error_message TEXT"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN error_message TEXT"))
        print("Added column: error_message")
    
    # Add brain_session_id (String(36), nullable=True, index=True) if missing
    if 'brain_session_id' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN brain_session_id VARCHAR(36)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scan_jobs_brain_session_id ON scan_jobs(brain_session_id)"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN brain_session_id VARCHAR(36)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_scan_jobs_brain_session_id ON scan_jobs(brain_session_id)"))
        print("Added column: brain_session_id")
    
    # Add summary (JSONB for PostgreSQL, JSON for SQLite) if missing
    if 'summary' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN summary JSONB"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN summary TEXT"))
        print("Added column: summary")
    
    # Add ai_plan (JSONB for PostgreSQL, JSON for SQLite) if missing
    if 'ai_plan' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN ai_plan JSONB"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN ai_plan TEXT"))
        print("Added column: ai_plan")
    
    # Add ai_status (String(20), nullable=True) if missing
    if 'ai_status' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN ai_status VARCHAR(20)"))
        else:
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN ai_status VARCHAR(20)"))
        print("Added column: ai_status")
    
    # Commit the transaction
    conn.commit()


def downgrade():
    """
    Remove columns added by this migration.
    Note: This will fail if columns are referenced elsewhere.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    # Check if table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'scan_jobs'
        )
    """)).scalar()
    
    if not table_exists:
        return
    
    # Get existing columns
    existing_columns = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """)).fetchall()
    existing_column_names = {row[0] for row in existing_columns}
    
    # Drop columns if they exist
    if 'stack_info' in existing_column_names:
        conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN IF EXISTS stack_info"))
    
    if 'scan_level' in existing_column_names:
        conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN IF EXISTS scan_level"))
        if is_postgresql:
            # Check if enum is used elsewhere before dropping
            enum_in_use = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE udt_name = 'scanlevel' AND table_name != 'scan_jobs'
                )
            """)).scalar()
            if not enum_in_use:
                conn.execute(text("DROP TYPE IF EXISTS scanlevel"))
    
    if 'celery_task_id' in existing_column_names:
        conn.execute(text("DROP INDEX IF EXISTS ix_scan_jobs_celery_task_id"))
        conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN IF EXISTS celery_task_id"))
    
    conn.commit()

