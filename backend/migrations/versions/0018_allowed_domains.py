"""add allowed_domains"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0018_allowed_domains"
down_revision = "0017_tool_result_skip_and_logs"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "allowed_domains" not in inspector.get_table_names():
        op.create_table(
            "allowed_domains",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("domain", sa.String(length=255), nullable=False, index=True),
            sa.Column("scope", sa.String(length=50), nullable=False, server_default="global", index=True),
            sa.Column("tenant_id", sa.String(length=36), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_admin_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )

    # create index if not exists
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_allowed_domains_domain_scope_tenant ON allowed_domains (domain, scope, tenant_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_allowed_domains_domain ON allowed_domains (domain)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_allowed_domains_scope ON allowed_domains (scope)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_allowed_domains_tenant_id ON allowed_domains (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_allowed_domains_created_by_admin_id ON allowed_domains (created_by_admin_id)")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "allowed_domains" in inspector.get_table_names():
        op.drop_table("allowed_domains")


