"""add user admin/approval and entitlements

Revision ID: 0016_add_user_admin_flags_and_entitlements
Revises: 0015_domain_verification_and_root_domain
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0016_add_user_admin_flags_and_entitlements"
down_revision = "0015_domain_verification_and_root_domain"
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'

    # Users: add columns if users table exists and columns are missing
    # Users table is created by migration 0020 (later in chain)
    if table_exists("users"):
        try:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "is_admin" not in user_cols:
                op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "is_approved" not in user_cols:
                op.add_column("users", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()))
        except Exception:
            # Users table may not be accessible yet
            pass

    # Entitlements table (create if missing)
    # Check if tenants and users exist (they may be created later by migration 0020)
    tenants_exists = table_exists("tenants")
    users_exists = table_exists("users")
    
    if "entitlements" not in inspector.get_table_names():
        # Only create table if tenants exists (for FK constraint)
        # If it doesn't exist, skip creation - migration 0020 or a later migration can create it
        if tenants_exists and users_exists:
            table_args = []
            if is_postgresql:
                table_args = [
                    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_entitlements_tenant_id'),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_entitlements_user_id'),
                ]
            
            # Use JSONB for PostgreSQL, Text for SQLite
            limits_json_type = postgresql.JSON() if is_postgresql else sa.Text()
            
            op.create_table(
                "entitlements",
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.String(length=36), nullable=False),
                sa.Column("user_id", sa.String(length=36), nullable=True),
                sa.Column("plan_name", sa.String(length=50), nullable=False),
                sa.Column("limits_json", limits_json_type, nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
                *table_args
            )
            # Create indexes idempotently (only if table was created)
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

    # Drop user columns if users table exists and columns are present
    if table_exists("users"):
        try:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "is_approved" in user_cols:
                op.drop_column("users", "is_approved")
            if "is_admin" in user_cols:
                op.drop_column("users", "is_admin")
        except Exception:
            pass

