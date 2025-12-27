"""add user admin/approval and entitlements

Revision ID: 0016_add_user_admin_flags_and_entitlements
Revises: 0015_domain_verification_and_root_domain
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_add_user_admin_flags_and_entitlements"
down_revision = "0015_domain_verification_and_root_domain"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Users: add columns if missing
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_admin" not in user_cols:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "is_approved" not in user_cols:
        op.add_column("users", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()))

    # Entitlements table (create if missing)
    if "entitlements" not in inspector.get_table_names():
        op.create_table(
            "entitlements",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("plan_name", sa.String(length=50), nullable=False),
            sa.Column("limits_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )
    # Create indexes idempotently
    op.execute("CREATE INDEX IF NOT EXISTS ix_entitlements_tenant_id ON entitlements (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entitlements_user_id ON entitlements (user_id)")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop indexes if exist
    op.execute("DROP INDEX IF EXISTS ix_entitlements_user_id")
    op.execute("DROP INDEX IF EXISTS ix_entitlements_tenant_id")

    # Drop table if exists
    if "entitlements" in inspector.get_table_names():
        op.execute("DROP TABLE IF EXISTS entitlements")

    # Drop user columns if present
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "is_approved" in user_cols:
        op.drop_column("users", "is_approved")
    if "is_admin" in user_cols:
        op.drop_column("users", "is_admin")

