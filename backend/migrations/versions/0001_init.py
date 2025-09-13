from alembic import op
import sqlalchemy as sa

revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.create_table('threat_item',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source', sa.Text, nullable=False),
        sa.Column('source_id', sa.Text),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('summary', sa.Text),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
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
        sa.Column('tags', sa.ARRAY(sa.Text), server_default='{}'),
        sa.Column('raw', sa.JSON)
    )
    op.create_index('threat_item_source_source_id_idx', 'threat_item', ['source','source_id'])
    op.create_table('threat_item_ref',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('threat_item_id', sa.UUID(as_uuid=True), sa.ForeignKey('threat_item.id', ondelete='CASCADE')),
        sa.Column('ref_type', sa.Text),
        sa.Column('ref_url', sa.Text)
    )

def downgrade():
    op.drop_table('threat_item_ref')
    op.drop_index('threat_item_source_source_id_idx', table_name='threat_item')
    op.drop_table('threat_item')
