"""add tool_result_id to findings

Revision ID: 0012_add_tool_result_id_to_findings
Revises: 0011_add_tool_run_tracking
Create Date: 2025-12-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0012_add_tool_result_id_to_findings'
down_revision = '0011_add_tool_run_tracking'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Check if column already exists
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('findings')]
    
    # Add tool_result_id column (nullable for backward compatibility with existing findings)
    if 'tool_result_id' not in existing_columns:
        op.add_column('findings', 
            sa.Column('tool_result_id', sa.String(36), nullable=True)
        )
    
    # Add foreign key constraint (if not SQLite, SQLite doesn't support ALTER TABLE ADD CONSTRAINT)
    if not is_sqlite:
        try:
            op.create_foreign_key(
                'fk_findings_tool_result_id',
                'findings',
                'tool_results',
                ['tool_result_id'],
                ['id'],
                ondelete='SET NULL'
            )
        except Exception as e:
            # Foreign key might already exist or table doesn't exist yet
            if 'already exists' not in str(e).lower() and 'no such table' not in str(e).lower():
                raise
    
    # Create index on tool_result_id for fast lookups
    try:
        op.create_index('ix_findings_tool_result_id', 'findings', ['tool_result_id'])
    except Exception:
        # Index might already exist, ignore
        pass


def downgrade():
    # Drop index
    try:
        op.drop_index('ix_findings_tool_result_id', 'findings')
    except Exception:
        pass
    
    # Drop foreign key (if not SQLite)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    if not is_sqlite:
        try:
            op.drop_constraint('fk_findings_tool_result_id', 'findings', type_='foreignkey')
        except Exception:
            pass
    
    # Drop column
    op.drop_column('findings', 'tool_result_id')


