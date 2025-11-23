from alembic import op
import sqlalchemy as sa

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
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
    op.create_index('threat_item_source_source_id_idx', 'threat_item', ['source','source_id'])
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
