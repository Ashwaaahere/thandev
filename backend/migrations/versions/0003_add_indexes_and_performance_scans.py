"""add indexes and performance scan jobs

Revision ID: 0003_add_indexes
Revises: 0002_add_scan_jobs_table
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003_add_indexes'
down_revision = '0002_add_scan_jobs_table'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Helper function to create index if it doesn't exist
    def create_index_if_not_exists(index_name, table_name, columns):
        try:
            op.create_index(index_name, table_name, columns)
        except Exception as e:
            # Index might already exist, check the error message
            if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                raise
    
    # Add indexes to threat_item table (with existence check)
    create_index_if_not_exists('idx_threat_item_published_at', 'threat_item', ['published_at'])
    create_index_if_not_exists('idx_threat_item_cve_id', 'threat_item', ['cve_id'])
    create_index_if_not_exists('idx_threat_item_is_kev', 'threat_item', ['is_kev'])
    create_index_if_not_exists('idx_threat_item_has_exploit', 'threat_item', ['has_exploit'])
    create_index_if_not_exists('idx_threat_item_source', 'threat_item', ['source'])
    
    # Add indexes to scan_jobs table (with existence check)
    create_index_if_not_exists('idx_scan_jobs_user_status', 'scan_jobs', ['user_id', 'status'])
    create_index_if_not_exists('idx_scan_jobs_created_at', 'scan_jobs', ['created_at'])
    
    # Add constraints to scan_jobs (SQLite doesn't support ALTER TABLE for constraints)
    if not is_sqlite:
        # PostgreSQL and other databases support ALTER TABLE
        op.create_check_constraint(
            'check_tier',
            'scan_jobs',
            "tier IN ('level0', 'level1', 'level2')"
        )
        op.create_check_constraint(
            'check_status',
            'scan_jobs',
            "status IN ('pending', 'running', 'completed', 'error')"
        )
    # For SQLite, constraints are enforced at the application level
    
    # Create performance_scan_jobs table
    # Check if PostgreSQL to use JSONB, otherwise use Text
    is_postgresql = bind.dialect.name == 'postgresql'
    
    if is_postgresql:
        result_type = postgresql.JSONB
    else:
        result_type = sa.Text
    
    # Create table with constraints (SQLite supports constraints in CREATE TABLE)
    table_args = []
    if not is_sqlite:
        # PostgreSQL supports check constraints
        table_args.extend([
            sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'error')", name='check_perf_status'),
            sa.CheckConstraint("device IN ('desktop', 'mobile')", name='check_device')
        ])
    
    op.create_table('performance_scan_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Text, nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('device', sa.String(20), server_default='desktop'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('result', result_type),
        sa.Column('error', sa.Text),
        *table_args
    )
    
    # Add indexes to performance_scan_jobs (with existence check)
    create_index_if_not_exists('idx_perf_scan_jobs_user_status', 'performance_scan_jobs', ['user_id', 'status'])
    create_index_if_not_exists('idx_perf_scan_jobs_created_at', 'performance_scan_jobs', ['created_at'])
    create_index_if_not_exists('idx_perf_scan_jobs_status', 'performance_scan_jobs', ['status'])
    create_index_if_not_exists('idx_perf_scan_jobs_user_id', 'performance_scan_jobs', ['user_id'])

def downgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Drop performance_scan_jobs table and indexes
    op.drop_index('idx_perf_scan_jobs_user_id', table_name='performance_scan_jobs')
    op.drop_index('idx_perf_scan_jobs_status', table_name='performance_scan_jobs')
    op.drop_index('idx_perf_scan_jobs_created_at', table_name='performance_scan_jobs')
    op.drop_index('idx_perf_scan_jobs_user_status', table_name='performance_scan_jobs')
    op.drop_table('performance_scan_jobs')
    
    # Drop constraints from scan_jobs (only for non-SQLite)
    if not is_sqlite:
        op.drop_constraint('check_status', 'scan_jobs', type_='check')
        op.drop_constraint('check_tier', 'scan_jobs', type_='check')
    
    # Drop indexes from scan_jobs
    op.drop_index('idx_scan_jobs_created_at', table_name='scan_jobs')
    op.drop_index('idx_scan_jobs_user_status', table_name='scan_jobs')
    
    # Drop indexes from threat_item
    op.drop_index('idx_threat_item_source', table_name='threat_item')
    op.drop_index('idx_threat_item_has_exploit', table_name='threat_item')
    op.drop_index('idx_threat_item_is_kev', table_name='threat_item')
    op.drop_index('idx_threat_item_cve_id', table_name='threat_item')
    op.drop_index('idx_threat_item_published_at', table_name='threat_item')

