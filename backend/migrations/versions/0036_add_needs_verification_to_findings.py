"""add needs_verification field to findings

Revision ID: 0036_add_needs_verification
Revises: 0035_add_project_urls_table
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0036_add_needs_verification'
down_revision = '0035_add_project_urls_table'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'findings' not in existing_tables:
        return
    
    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns('findings')]
    if 'needs_verification' in columns:
        return
    
    # Add needs_verification column
    if is_sqlite:
        # SQLite doesn't support ALTER COLUMN with default, so we need to recreate
        # For now, just add the column without default (will be handled by app default)
        op.add_column('findings', sa.Column('needs_verification', sa.Boolean(), nullable=True))
        # Update existing rows to False
        op.execute("UPDATE findings SET needs_verification = 0 WHERE needs_verification IS NULL")
        # Make it NOT NULL (SQLite limitation: can't do this in one step easily)
        # We'll rely on app-level default for new rows
    else:
        # PostgreSQL
        op.add_column('findings', sa.Column('needs_verification', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'findings' not in existing_tables:
        return
    
    columns = [col['name'] for col in inspector.get_columns('findings')]
    if 'needs_verification' not in columns:
        return
    
    op.drop_column('findings', 'needs_verification')

