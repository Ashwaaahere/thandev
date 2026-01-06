from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0001_init'
down_revision = '0000_fix_alembic_version'
branch_labels = None
depends_on = None

def table_exists(table_name):
    """Check if a table exists in the database"""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()

def upgrade():
    # Check if tables already exist (for cases where they were created manually)
    if not table_exists('threat_item'):
        # SQLite doesn't support extensions, skip UUID extension
        op.create_table('threat_item',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('source', sa.Text, nullable=False),
            sa.Column('source_id', sa.Text),
            sa.Column('title', sa.Text, nullable=False),
            sa.Column('summary', sa.Text),
            sa.Column('published_at', sa.DateTime(timezone=True)),
            sa.Column('discovered_at', sa.DateTime(timezone=True)),
            sa.Column('url', sa.Text),
            sa.Column('cve_id', sa.Text),
            sa.Column('cwe_id', sa.Text),
            sa.Column('vendor', sa.Text),
            sa.Column('product', sa.Text),
            sa.Column('version_range', sa.Text),
            sa.Column('cvss_v2', sa.Numeric),
            sa.Column('cvss_v3', sa.Numeric),
            sa.Column('epss_score', sa.Numeric),
            sa.Column('is_kev', sa.Boolean, server_default=sa.text('false')),
            sa.Column('has_exploit', sa.Boolean, server_default=sa.text('false')),
            sa.Column('tags', sa.Text),  # JSON stored as text in SQLite
            sa.Column('raw', sa.Text)  # JSON stored as text in SQLite
        )
    
    # Create index if it doesn't exist
    try:
        op.create_index('threat_item_source_source_id_idx', 'threat_item', ['source','source_id'])
    except Exception as e:
        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
            raise
    
    if not table_exists('threat_item_ref'):
        op.create_table('threat_item_ref',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('threat_item_id', sa.String(36), sa.ForeignKey('threat_item.id', ondelete='CASCADE')),
            sa.Column('ref_type', sa.Text),
            sa.Column('ref_url', sa.Text)
        )

def downgrade():
    op.drop_table('threat_item_ref')
    op.drop_index('threat_item_source_source_id_idx', table_name='threat_item')
    op.drop_table('threat_item')
