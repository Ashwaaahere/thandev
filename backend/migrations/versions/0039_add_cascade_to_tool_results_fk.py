"""add cascade delete to tool_results foreign key

Revision ID: 0039_add_cascade_to_tool_results_fk
Revises: 0038_add_scan_events
Create Date: 2025-01-13

This migration adds CASCADE delete to the tool_results.scan_job_id foreign key
to ensure tool results are properly deleted when scans are deleted.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0039_add_cascade_to_tool_results_fk'
down_revision = '0038_add_scan_events'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add CASCADE delete to tool_results.scan_job_id foreign key.
    
    This ensures that when a scan_job is deleted, all related tool_results
    are automatically deleted at the database level, preventing orphaned records.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Check if tool_results table exists
    existing_tables = inspector.get_table_names()
    if 'tool_results' not in existing_tables:
        print("tool_results table does not exist, skipping foreign key update")
        return
    
    # Get existing foreign key constraints
    fk_constraints = inspector.get_foreign_keys('tool_results')
    scan_job_fk = None
    for fk in fk_constraints:
        if 'scan_job_id' in fk['constrained_columns']:
            scan_job_fk = fk
            break
    
    if not scan_job_fk:
        print("No foreign key constraint found on scan_job_id, creating one with CASCADE")
        # Create the foreign key with CASCADE if it doesn't exist
        if is_postgresql:
            op.create_foreign_key(
                'fk_tool_results_scan_job_id',
                'tool_results',
                'scan_jobs',
                ['scan_job_id'],
                ['id'],
                ondelete='CASCADE'
            )
        elif is_sqlite:
            # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we skip
            print("SQLite doesn't support adding foreign key constraints via ALTER TABLE, skipping")
        return
    
    # Check if CASCADE is already set
    if is_postgresql:
        # For PostgreSQL, we need to drop and recreate the constraint
        constraint_name = scan_job_fk['name']
        print(f"Dropping existing foreign key constraint: {constraint_name}")
        op.drop_constraint(constraint_name, 'tool_results', type_='foreignkey')
        
        print("Creating foreign key constraint with CASCADE delete")
        op.create_foreign_key(
            constraint_name,
            'tool_results',
            'scan_jobs',
            ['scan_job_id'],
            ['id'],
            ondelete='CASCADE'
        )
        print("Successfully added CASCADE delete to tool_results.scan_job_id foreign key")
    elif is_sqlite:
        # SQLite doesn't support modifying foreign key constraints
        # The cascade behavior is handled by SQLAlchemy relationships
        print("SQLite detected - CASCADE is handled by SQLAlchemy relationships, skipping database-level constraint update")


def downgrade():
    """
    Remove CASCADE delete from tool_results.scan_job_id foreign key.
    
    Note: This will restore the previous behavior where tool_results
    might become orphaned if scans are deleted directly at the database level.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        print("SQLite detected - skipping downgrade (constraints handled by SQLAlchemy)")
        return
    
    # Get existing foreign key constraints
    fk_constraints = inspector.get_foreign_keys('tool_results')
    scan_job_fk = None
    for fk in fk_constraints:
        if 'scan_job_id' in fk['constrained_columns']:
            scan_job_fk = fk
            break
    
    if scan_job_fk and is_postgresql:
        constraint_name = scan_job_fk['name']
        print(f"Dropping CASCADE foreign key constraint: {constraint_name}")
        op.drop_constraint(constraint_name, 'tool_results', type_='foreignkey')
        
        print("Recreating foreign key constraint without CASCADE")
        op.create_foreign_key(
            constraint_name,
            'tool_results',
            'scan_jobs',
            ['scan_job_id'],
            ['id']
            # No ondelete specified - defaults to RESTRICT/NO ACTION
        )
        print("Successfully removed CASCADE delete from tool_results.scan_job_id foreign key")

