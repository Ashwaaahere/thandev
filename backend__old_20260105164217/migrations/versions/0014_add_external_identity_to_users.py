"""add_external_identity_to_users

Revision ID: 0014
Revises: 0013
Create Date: 2025-12-26 00:57:00.000000

Note: This migration adds columns to users table. If users table doesn't exist yet
(created later by migration 0020), this migration will be a no-op. The columns
will be created as part of 0020 when the users table is created.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '0014_add_external_identity_to_users'
down_revision = '0013_create_notifications_table'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        columns = inspector.get_columns(table_name)
        return any(col['name'] == column_name for col in columns)
    except Exception:
        # Table doesn't exist
        return False


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # Check if users table exists (it may be created later by migration 0020)
    if not table_exists('users'):
        # Users table doesn't exist yet - skip this migration
        # The columns will be created as part of migration 0020
        return
    
    # Users table exists - add columns if they don't already exist
    # (Migration 0020 may have already created them)
    if not column_exists('users', 'external_provider'):
        op.add_column('users', sa.Column('external_provider', sa.String(length=50), nullable=True))
    
    if not column_exists('users', 'external_user_id'):
        op.add_column('users', sa.Column('external_user_id', sa.String(length=255), nullable=True))
    
    # Add indexes for faster lookups (with existence check)
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = inspector.get_indexes('users')
    index_names = {idx['name'] for idx in indexes}
    
    if 'ix_users_external_provider' not in index_names:
        try:
            op.create_index(op.f('ix_users_external_provider'), 'users', ['external_provider'], unique=False)
        except Exception:
            pass  # Index may already exist
    
    if 'ix_users_external_user_id' not in index_names:
        try:
            op.create_index(op.f('ix_users_external_user_id'), 'users', ['external_user_id'], unique=False)
        except Exception:
            pass  # Index may already exist
    
    # Add unique constraint on (external_provider, external_user_id) if not exists
    # Check if constraint already exists (migration 0020 may have created it)
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'
    
    if is_postgresql:
        # Check if constraint exists using inspector
        fks = inspector.get_foreign_keys('users')
        unique_constraints = inspector.get_unique_constraints('users')
        constraint_names = {c['name'] for c in unique_constraints}
        constraint_exists = 'uq_users_external_identity' in constraint_names
        
        if not constraint_exists:
            try:
                op.create_unique_constraint('uq_users_external_identity', 'users', ['external_provider', 'external_user_id'])
            except Exception:
                pass  # Constraint may already exist
    else:
        # SQLite - try to create, catch if exists
        try:
            op.create_unique_constraint('uq_users_external_identity', 'users', ['external_provider', 'external_user_id'])
        except Exception:
            pass  # Constraint may already exist


def downgrade():
    # Only downgrade if users table exists and columns exist
    if not table_exists('users'):
        return
    
    # Remove unique constraint (if exists)
    try:
        op.drop_constraint('uq_users_external_identity', 'users', type_='unique')
    except Exception:
        pass
    
    # Remove indexes (if exist)
    try:
        op.drop_index(op.f('ix_users_external_user_id'), table_name='users')
    except Exception:
        pass
    
    try:
        op.drop_index(op.f('ix_users_external_provider'), table_name='users')
    except Exception:
        pass
    
    # Remove columns (if exist)
    if column_exists('users', 'external_user_id'):
        op.drop_column('users', 'external_user_id')
    
    if column_exists('users', 'external_provider'):
        op.drop_column('users', 'external_provider')

