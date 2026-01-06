"""add scan_level and stack_info columns to scan_jobs

Revision ID: 0022_add_scan_jobs_columns
Revises: 0021_add_project_id_to_scan_jobs
Create Date: 2024-12-29 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '0022_add_scan_jobs_columns'
down_revision = '0021_add_project_id_to_scan_jobs'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add missing columns to scan_jobs table if they don't exist.
    This migration is idempotent and safe to run multiple times.
    """
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns for scan_jobs table
    columns = {col['name']: col for col in inspector.get_columns('scan_jobs')}
    
    # Add scan_level column if it doesn't exist
    if 'scan_level' not in columns:
        if conn.dialect.name == 'postgresql':
            # Check if enum type exists
            enum_exists = conn.execute(sa.text("""
                SELECT 1 FROM pg_type WHERE typname = 'scanlevel'
            """)).scalar()
            
            if not enum_exists:
                # Create the enum type
                op.execute("CREATE TYPE scanlevel AS ENUM ('basic', 'pro', 'advanced')")
            
            # Add column with enum type and temporary default
            op.add_column('scan_jobs', 
                sa.Column('scan_level', sa.Enum('basic', 'pro', 'advanced', name='scanlevel', create_type=False), 
                         nullable=False, server_default='basic'))
            # Remove server_default after adding (so future inserts require explicit value)
            op.alter_column('scan_jobs', 'scan_level', server_default=None)
    else:
        # For SQLite and other databases, use String instead of Enum
        if 'scan_level' not in columns:
            op.add_column('scan_jobs', 
                sa.Column('scan_level', sa.String(20), nullable=False, server_default='basic'))
            op.alter_column('scan_jobs', 'scan_level', server_default=None)
    
    # Add stack_info column if it doesn't exist (JSONB for PostgreSQL, JSON for others)
    if 'stack_info' not in columns:
        if conn.dialect.name == 'postgresql':
            op.add_column('scan_jobs', 
                sa.Column('stack_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        else:
            op.add_column('scan_jobs', 
                sa.Column('stack_info', sa.JSON(), nullable=True))


def downgrade():
    """
    Remove the added columns. 
    Note: This will fail if there are constraints or indexes on these columns.
    """
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {col['name']: col for col in inspector.get_columns('scan_jobs')}
    
    if 'stack_info' in columns:
        op.drop_column('scan_jobs', 'stack_info')
    
    if 'scan_level' in columns:
        op.drop_column('scan_jobs', 'scan_level')
        # Drop enum type if it exists (PostgreSQL only)
        if conn.dialect.name == 'postgresql':
            # Check if enum is still in use
            enum_in_use = conn.execute(sa.text("""
                SELECT 1 FROM information_schema.columns 
                WHERE udt_name = 'scanlevel' AND table_name != 'scan_jobs'
            """)).scalar()
            if not enum_in_use:
                op.execute("DROP TYPE IF EXISTS scanlevel")
