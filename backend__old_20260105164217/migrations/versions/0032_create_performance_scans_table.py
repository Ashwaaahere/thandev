"""create performance_scans table aligned with ORM model

Revision ID: 0032_create_performance_scans_table
Revises: 0030_add_missing_findings_columns
Create Date: 2026-01-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0032_create_performance_scans_table"
# Align down_revision with last existing migration
down_revision = "0030_add_missing_findings_columns"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "performance_scans" in existing_tables:
        return

    # Use JSONB for Postgres, JSON for others
    json_type = postgresql.JSONB if bind.dialect.name == "postgresql" else sa.JSON

    if bind.dialect.name == "postgresql":
        scanlevel_enum = postgresql.ENUM("basic", "pro", "advanced", name="scanlevel", create_type=False)
        status_enum = postgresql.ENUM("queued", "running", "completed", "failed", name="performancescanstatus", create_type=True)
    else:
        scanlevel_enum = sa.Enum("basic", "pro", "advanced", name="scanlevel")
        status_enum = sa.Enum("queued", "running", "completed", "failed", name="performancescanstatus")

    op.create_table(
        "performance_scans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("scan_level", scanlevel_enum, nullable=False),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            index=True,
            server_default="queued",
        ),
        sa.Column("metrics", json_type, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    if "performance_scans" in existing_tables:
        op.drop_table("performance_scans")

