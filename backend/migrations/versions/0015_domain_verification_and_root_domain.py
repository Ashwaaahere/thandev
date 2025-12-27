"""add domain_verifications and project root_domain

Revision ID: 0015_domain_verification_and_root_domain
Revises: 0014_add_external_identity_to_users
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0015_domain_verification_and_root_domain"
down_revision = "0014b_create_core_tables_pre_0015"
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # Ensure enum exists (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'domain_verification_status'
            ) THEN
                CREATE TYPE domain_verification_status AS ENUM ('pending', 'verified', 'failed', 'expired');
            END IF;
        END$$;
        """
    )

    # SQLAlchemy enum uses existing type (no create)
    domain_status_enum = postgresql.ENUM(
        "pending", "verified", "failed", "expired",
        name="domain_verification_status",
        create_type=False,
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_postgresql = bind.dialect.name == 'postgresql'

    # Add root_domain to projects if projects table exists and column is missing
    # Projects table is created by migration 0020 (later in chain)
    if table_exists("projects"):
        try:
            project_cols = {c["name"] for c in inspector.get_columns("projects")}
            if "root_domain" not in project_cols:
                op.add_column("projects", sa.Column("root_domain", sa.String(length=255), nullable=True))
                op.execute("CREATE INDEX IF NOT EXISTS ix_projects_root_domain ON projects (root_domain)")
        except Exception:
            # Projects table may not be accessible yet
            pass

    # Create domain_verifications table if missing
    # Check if tenants and projects exist (they may be created later by migration 0020)
    tenants_exists = table_exists("tenants")
    projects_exists = table_exists("projects")
    
    if "domain_verifications" not in inspector.get_table_names():
        # Only create table if both tenants and projects exist (for FK constraints)
        # If they don't exist, skip creation - migration 0020 or a later migration can create it
        if tenants_exists and projects_exists:
            table_args = []
            if is_postgresql:
                table_args = [
                    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_domain_verifications_tenant_id'),
                    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_domain_verifications_project_id'),
                ]
            
            op.create_table(
                "domain_verifications",
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("tenant_id", sa.String(length=36), nullable=False),
                sa.Column("project_id", sa.String(length=36), nullable=False),
                sa.Column("domain", sa.String(length=255), nullable=False),
                sa.Column("status", domain_status_enum, nullable=False),
                sa.Column("token", sa.String(length=255), nullable=False),
                sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("last_error", sa.Text(), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
                *table_args
            )
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_domain_verifications_project_domain "
                "ON domain_verifications (project_id, domain)"
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "domain_verifications" in inspector.get_table_names():
        op.execute("DROP TABLE IF EXISTS domain_verifications")

    op.execute("DROP TYPE IF EXISTS domain_verification_status")

    # Only drop column if projects table exists
    if table_exists("projects"):
        try:
            project_cols = {c["name"] for c in inspector.get_columns("projects")}
            if "root_domain" in project_cols:
                op.execute("DROP INDEX IF EXISTS ix_projects_root_domain")
                op.drop_column("projects", "root_domain")
        except Exception:
            pass

