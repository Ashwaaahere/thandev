"""add skip reason and raw logs to tool_results

Revision ID: 0017_tool_result_skip_and_logs
Revises: 0016_add_user_admin_flags_and_entitlements
Create Date: 2025-12-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_tool_result_skip_and_logs"
down_revision = "0016_add_user_admin_flags_and_entitlements"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tool_results", sa.Column("skip_reason", sa.String(length=100), nullable=True))
    op.add_column("tool_results", sa.Column("raw_stdout", sa.Text(), nullable=True))
    op.add_column("tool_results", sa.Column("raw_stderr", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("tool_results", "raw_stderr")
    op.drop_column("tool_results", "raw_stdout")
    op.drop_column("tool_results", "skip_reason")

