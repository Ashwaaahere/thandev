"""add_external_identity_to_users

Revision ID: 0014
Revises: 0013
Create Date: 2025-12-26 00:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_add_external_identity_to_users'
down_revision = '0013_create_notifications_table'
branch_labels = None
depends_on = None


def upgrade():
    # Add external identity columns to users table
    op.add_column('users', sa.Column('external_provider', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('external_user_id', sa.String(length=255), nullable=True))
    
    # Add indexes for faster lookups
    op.create_index(op.f('ix_users_external_provider'), 'users', ['external_provider'], unique=False)
    op.create_index(op.f('ix_users_external_user_id'), 'users', ['external_user_id'], unique=False)
    
    # Add unique constraint on (external_provider, external_user_id)
    op.create_unique_constraint('uq_users_external_identity', 'users', ['external_provider', 'external_user_id'])


def downgrade():
    # Remove unique constraint
    op.drop_constraint('uq_users_external_identity', 'users', type_='unique')
    
    # Remove indexes
    op.drop_index(op.f('ix_users_external_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_external_provider'), table_name='users')
    
    # Remove columns
    op.drop_column('users', 'external_user_id')
    op.drop_column('users', 'external_provider')

