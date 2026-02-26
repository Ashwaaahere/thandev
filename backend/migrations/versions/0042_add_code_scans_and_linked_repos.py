"""add code_scans and linked_repos tables

Revision ID: 0042_add_code_scans_and_linked_repos
Revises: 0041
Create Date: 2026-02-24

This migration adds:
- linked_repos: allowlist of CI-connected repos per project and provider
- code_scans: records for CI-ingested code scan runs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
import logging


# revision identifiers, used by Alembic.
revision = "0042_add_code_scans_and_linked_repos"
down_revision = "0041"
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create linked_repos and code_scans tables (idempotent)."""
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    # Use JSONB for PostgreSQL, JSON for SQLite/others
    if is_postgresql:
        json_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        json_type = sa.JSON()

    # 1. linked_repos: allowlist of repos that are allowed to send code scans
    if not table_exists("linked_repos"):
        logger.info("Creating linked_repos table...")
        op.create_table(
            "linked_repos",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "provider",
                sa.String(32),
                nullable=False,
                comment="CI provider: github, bitbucket, gitlab, circleci, azuredevops",
            ),
            sa.Column(
                "repo_full_name",
                sa.Text(),
                nullable=False,
                comment="Provider-native repository identifier (e.g. owner/repo)",
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "allowed_refs",
                json_type,
                nullable=True,
                comment="Optional list of allowed refs/branches/tags",
            ),
            sa.Column(
                "allowed_workflows",
                json_type,
                nullable=True,
                comment="Optional list of allowed workflow identifiers",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "project_id",
                "provider",
                "repo_full_name",
                name="uq_linked_repos_project_provider_repo",
            ),
        )
        op.create_index(
            "idx_linked_repos_project_id", "linked_repos", ["project_id"]
        )
        op.create_index(
            "idx_linked_repos_provider_repo",
            "linked_repos",
            ["provider", "repo_full_name"],
        )
        logger.info("✓ linked_repos table created")
    else:
        logger.info("linked_repos table already exists, skipping")

    # 2. code_scans: records for CI-ingested code scan runs
    if not table_exists("code_scans"):
        logger.info("Creating code_scans table...")
        op.create_table(
            "code_scans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "scan_type",
                sa.String(16),
                nullable=False,
                server_default="code",
                comment="Type of scan (currently always 'code')",
            ),
            sa.Column(
                "provider",
                sa.String(32),
                nullable=False,
                comment="CI provider: github, bitbucket, gitlab, circleci, azuredevops",
            ),
            sa.Column(
                "repo_full_name",
                sa.Text(),
                nullable=False,
                comment="Provider-native repository identifier",
            ),
            sa.Column("ref", sa.Text(), nullable=True),
            sa.Column("sha", sa.Text(), nullable=True),
            sa.Column(
                "run_id",
                sa.Text(),
                nullable=True,
                comment="Provider-native run/pipeline identifier",
            ),
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="running",
                comment="Code scan status: running, completed, failed",
            ),
            sa.Column(
                "summary_json",
                json_type,
                nullable=True,
                comment="Aggregated summary counts, including per-source SCA counts",
            ),
            sa.Column(
                "meta_json",
                json_type,
                nullable=True,
                comment="Pipeline metadata (run URL, actor, workflow, artifacts, etc.)",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Index("idx_code_scans_project_id", "project_id"),
            sa.Index("idx_code_scans_provider_repo", "provider", "repo_full_name"),
            sa.Index(
                "idx_code_scans_provider_repo_run",
                "provider",
                "repo_full_name",
                "run_id",
            ),
        )
        logger.info("✓ code_scans table created")
    else:
        logger.info("code_scans table already exists, skipping")


def downgrade() -> None:
    """Drop code_scans and linked_repos tables."""
    # Drop in reverse dependency order
    try:
        op.drop_table("code_scans")
        logger.info("✓ Dropped code_scans table")
    except Exception as e:
        logger.warning(f"Could not drop code_scans table: {e}")

    try:
        op.drop_table("linked_repos")
        logger.info("✓ Dropped linked_repos table")
    except Exception as e:
        logger.warning(f"Could not drop linked_repos table: {e}")

