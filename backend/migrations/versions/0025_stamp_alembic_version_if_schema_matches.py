"""stamp alembic version if schema matches head

Revision ID: 0025_stamp_version
Revises: 0024_rename_finished_at
Create Date: 2025-12-30 02:30:00.000000

This migration helps fix cases where the schema was updated but alembic_version wasn't.
It checks if scan_jobs has the expected columns from 0023 and 0024, and if so,
stamps the version to match the current head.

IMPORTANT: This is a one-time fix migration. It only stamps if schema appears correct.
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0025_stamp_version'
down_revision = '0024_rename_finished_at'
branch_labels = None
depends_on = None


def upgrade():
    """
    Check if schema matches head (0024), and if alembic_version is behind, update it.
    This is safe because we only stamp if columns exist.
    """
    conn = op.get_bind()
    is_postgresql = conn.dialect.name == 'postgresql'
    
    # Check if alembic_version table exists
    table_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'alembic_version'
        )
    """)).scalar()
    
    if not table_exists:
        # Create alembic_version table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """))
        conn.commit()
        print("Created alembic_version table")
    
    # Get current version
    current_version_result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    current_version = current_version_result.scalar() if current_version_result.rowcount > 0 else None
    
    # Check if scan_jobs has columns from 0023 and 0024 (completed_at should exist after 0024)
    scan_jobs_columns_result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """))
    scan_jobs_columns = {row[0] for row in scan_jobs_columns_result.fetchall()}
    
    # Expected columns after 0024
    expected_columns_0024 = {
        'id', 'project_id', 'scan_level', 'status', 'celery_task_id',
        'brain_session_id', 'summary', 'stack_info', 'ai_plan', 'ai_status',
        'error_message', 'created_at', 'started_at', 'completed_at'  # completed_at should exist after 0024
    }
    
    # Check if we have all expected columns
    missing_columns = expected_columns_0024 - scan_jobs_columns
    
    # If we're missing completed_at but have finished_at, that's OK (0024 will rename it)
    has_finished_at = 'finished_at' in scan_jobs_columns
    has_completed_at = 'completed_at' in scan_jobs_columns
    
    if has_finished_at and not has_completed_at:
        # Before 0024 runs, this is expected
        missing_columns.discard('completed_at')
    
    # If schema appears correct (all expected columns present or will be renamed),
    # and version is behind 0024, stamp it
    if not missing_columns and current_version != '0024_rename_finished_at':
        # Only stamp if we're significantly behind (0022 or earlier)
        # This prevents accidentally stamping during normal migration flow
        if current_version is None or current_version < '0023_fix_scan_jobs_columns':
            print(f"Schema appears correct but version is {current_version}, stamping to 0024")
            # Delete old version if exists
            conn.execute(text("DELETE FROM alembic_version"))
            # Insert new version
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0024_rename_finished_at')"))
            conn.commit()
        else:
            print(f"Current version is {current_version}, not stamping (let normal migration flow handle it)")
    else:
        if missing_columns:
            print(f"Schema not ready for stamping, missing columns: {missing_columns}")
        else:
            print(f"Version is already correct: {current_version}")


def downgrade():
    """
    No-op for downgrade - we don't want to revert version stamps.
    """
    pass

