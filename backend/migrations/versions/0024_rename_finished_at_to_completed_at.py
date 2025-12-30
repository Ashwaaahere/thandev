"""rename finished_at to completed_at in scan_jobs

Revision ID: 0024_rename_finished_at
Revises: 0023_fix_scan_jobs_columns
Create Date: 2025-12-30 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0024_rename_finished_at'
down_revision = '0023_fix_scan_jobs_columns'
branch_labels = None
depends_on = None


def upgrade():
    """
    Rename finished_at to completed_at in scan_jobs table.
    This is idempotent - checks if column exists before renaming.
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
        print("scan_jobs table does not exist, skipping column rename")
        return
    
    # Get existing columns
    existing_columns = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'scan_jobs'
    """)).fetchall()
    existing_column_names = {row[0] for row in existing_columns}
    
    # Rename finished_at to completed_at if finished_at exists and completed_at doesn't
    if 'finished_at' in existing_column_names and 'completed_at' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs RENAME COLUMN finished_at TO completed_at"))
        else:
            # SQLite doesn't support RENAME COLUMN directly, need to recreate
            # For SQLite, we'll copy data to new column and drop old
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN completed_at TIMESTAMP"))
            conn.execute(text("UPDATE scan_jobs SET completed_at = finished_at WHERE finished_at IS NOT NULL"))
            conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN finished_at"))
        print("Renamed column: finished_at -> completed_at")
    elif 'completed_at' in existing_column_names:
        print("Column completed_at already exists, skipping rename")
    else:
        print("Column finished_at does not exist, skipping rename")
    
    conn.commit()


def downgrade():
    """
    Rename completed_at back to finished_at.
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
    
    # Rename completed_at back to finished_at if completed_at exists and finished_at doesn't
    if 'completed_at' in existing_column_names and 'finished_at' not in existing_column_names:
        if is_postgresql:
            conn.execute(text("ALTER TABLE scan_jobs RENAME COLUMN completed_at TO finished_at"))
        else:
            # SQLite workaround
            conn.execute(text("ALTER TABLE scan_jobs ADD COLUMN finished_at TIMESTAMP"))
            conn.execute(text("UPDATE scan_jobs SET finished_at = completed_at WHERE completed_at IS NOT NULL"))
            conn.execute(text("ALTER TABLE scan_jobs DROP COLUMN completed_at"))
    
    conn.commit()

