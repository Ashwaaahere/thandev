from alembic import op
import sqlalchemy as sa

revision = '0002_add_scan_jobs_table'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade():
    # Check if table already exists (for SQLite compatibility)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if 'scan_jobs' not in existing_tables:
        op.create_table('scan_jobs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.Text, nullable=False),
            sa.Column('url', sa.Text, nullable=False),
            sa.Column('domain', sa.Text),
            sa.Column('tier', sa.String(10), nullable=False),
            sa.Column('status', sa.String(20), server_default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('finished_at', sa.DateTime(timezone=True)),
            sa.Column('artifact_urls', sa.Text),  # JSON stored as text in SQLite
            sa.Column('summary', sa.Text),  # JSON stored as text in SQLite
            sa.Column('preset_version', sa.String(20), server_default='1.0'),
            sa.Column('execution_id', sa.Text)
        )
    
    # Create indexes if they don't exist
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('scan_jobs')] if 'scan_jobs' in existing_tables else []
    
    if 'scan_jobs_user_id_idx' not in existing_indexes:
        try:
            op.create_index('scan_jobs_user_id_idx', 'scan_jobs', ['user_id'])
        except Exception:
            pass  # Index might already exist
    if 'scan_jobs_tier_idx' not in existing_indexes:
        try:
            op.create_index('scan_jobs_tier_idx', 'scan_jobs', ['tier'])
        except Exception:
            pass
    if 'scan_jobs_status_idx' not in existing_indexes:
        try:
            op.create_index('scan_jobs_status_idx', 'scan_jobs', ['status'])
        except Exception:
            pass

def downgrade():
    op.drop_index('scan_jobs_status_idx', table_name='scan_jobs')
    op.drop_index('scan_jobs_tier_idx', table_name='scan_jobs')
    op.drop_index('scan_jobs_user_id_idx', table_name='scan_jobs')
    op.drop_table('scan_jobs')

