"""add lifecycle and remediation fields to findings

Revision ID: 0008_add_findings_lifecycle
Revises: 0007_add_audit_logs_table
Create Date: 2025-01-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0008_add_findings_lifecycle'
down_revision = '0007'  # Matches revision ID in 0007_add_audit_logs_table.py
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create findings table if it doesn't exist
    if 'findings' not in existing_tables:
        op.create_table('findings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('scan_job_id', sa.String(36), sa.ForeignKey('scan_jobs.id'), nullable=False),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('severity', sa.String(20), nullable=False),  # Will be enum in app
            sa.Column('cve_id', sa.String(50), nullable=True),
            sa.Column('cwe_id', sa.String(50), nullable=True),
            sa.Column('cvss_score', sa.Float, nullable=True),
            sa.Column('tool_name', sa.String(100), nullable=True),
            sa.Column('template_id', sa.String(255), nullable=True),
            sa.Column('rule_id', sa.String(255), nullable=True),
            sa.Column('vuln_type', sa.String(100), nullable=True),
            sa.Column('category', sa.String(100), nullable=True),
            sa.Column('url', sa.String(2048), nullable=True),
            sa.Column('path', sa.String(2048), nullable=True),
            sa.Column('line_number', sa.Integer, nullable=True),
            sa.Column('http_method', sa.String(10), nullable=True),
            sa.Column('parameter', sa.String(255), nullable=True),
            sa.Column('header_name', sa.String(255), nullable=True),
            sa.Column('cookie_name', sa.String(255), nullable=True),
            sa.Column('evidence', sa.Text, nullable=True),
            sa.Column('status', sa.String(20), nullable=True),  # Will be enum in app
            sa.Column('dedup_key', sa.String(64), nullable=True),
            sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_seen_in_scan_id', sa.String(36), sa.ForeignKey('scan_jobs.id'), nullable=True),
            sa.Column('found_count', sa.Integer, nullable=False, server_default='1'),
            sa.Column('not_seen_in_latest_scan', sa.Boolean if not is_sqlite else sa.Integer, nullable=False, server_default='false' if not is_sqlite else '0'),
            sa.Column('remediation_summary', sa.Text, nullable=True),
            sa.Column('remediation_steps', sa.Text, nullable=True),
            sa.Column('framework_hint', sa.String(100), nullable=True),
            sa.Column('project_id', sa.String(36), nullable=True),  # Add project_id to table creation
            sa.Column('tool', sa.String(100), nullable=True),  # Add tool to table creation
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        )
        # Create indexes
        op.create_index('ix_findings_scan_job_id', 'findings', ['scan_job_id'])
        op.create_index('ix_findings_severity', 'findings', ['severity'])
        op.create_index('ix_findings_tool_name', 'findings', ['tool_name'])
        op.create_index('ix_findings_cve_id', 'findings', ['cve_id'])
        op.create_index('ix_findings_vuln_type', 'findings', ['vuln_type'])
        op.create_index('ix_findings_template_id', 'findings', ['template_id'])
        op.create_index('ix_findings_dedup_key', 'findings', ['dedup_key'])
        op.create_index('ix_findings_project_id', 'findings', ['project_id'])
        op.create_index('ix_findings_tool', 'findings', ['tool'])
    
    # Check existing columns (refresh after table creation)
    if 'findings' in existing_tables or 'findings' not in [t for t in inspector.get_table_names()]:
        inspector = sa.inspect(bind)  # Refresh inspector
    existing_columns = [col['name'] for col in inspector.get_columns('findings')] if 'findings' in inspector.get_table_names() else []
    
    # Add project_id column (direct link to projects) if it doesn't exist
    if 'project_id' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('project_id', sa.String(36), nullable=True)
            )
        except Exception:
            pass  # Column might already exist
        # Create index if it doesn't exist
        try:
            op.create_index('ix_findings_project_id', 'findings', ['project_id'])
        except Exception:
            pass  # Index might already exist
        # Add foreign key constraint (if not SQLite, as SQLite has limited FK support)
        if not is_sqlite:
            try:
                op.create_foreign_key(
                    'fk_findings_project_id',
                    'findings', 'projects',
                    ['project_id'], ['id']
                )
            except Exception:
                pass  # FK might already exist
    
    # Add tool column (normalized tool name) if it doesn't exist
    if 'tool' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('tool', sa.String(100), nullable=True)
            )
            op.create_index('ix_findings_tool', 'findings', ['tool'])
        except Exception as e:
            if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
                raise
    
    # Add template_id and rule_id if they don't exist
    if 'template_id' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('template_id', sa.String(255), nullable=True)
            )
            op.create_index('ix_findings_template_id', 'findings', ['template_id'])
        except Exception:
            pass
    if 'rule_id' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('rule_id', sa.String(255), nullable=True)
            )
        except Exception:
            pass
    
    # Add vuln_type and category if they don't exist
    if 'vuln_type' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('vuln_type', sa.String(100), nullable=True)
            )
            op.create_index('ix_findings_vuln_type', 'findings', ['vuln_type'])
        except Exception:
            pass
    if 'category' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('category', sa.String(100), nullable=True)
            )
        except Exception:
            pass
    
    # Add location fields if they don't exist
    for col_name, col_type, col_length in [
        ('http_method', sa.String, 10),
        ('parameter', sa.String, 255),
        ('header_name', sa.String, 255),
        ('cookie_name', sa.String, 255),
    ]:
        if col_name not in existing_columns:
            try:
                op.add_column('findings', 
                    sa.Column(col_name, col_type(col_length), nullable=True)
                )
            except Exception:
                pass
    
    # Add evidence field if it doesn't exist
    if 'evidence' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('evidence', sa.Text(), nullable=True)
            )
        except Exception:
            pass
    
    # Add lifecycle fields if they don't exist
    if 'dedup_key' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('dedup_key', sa.String(64), nullable=True)
            )
            op.create_index('ix_findings_dedup_key', 'findings', ['dedup_key'])
        except Exception:
            pass
    for col_name in ['first_seen_at', 'last_seen_at']:
        if col_name not in existing_columns:
            try:
                op.add_column('findings', 
                    sa.Column(col_name, sa.DateTime(timezone=True), nullable=True)
                )
            except Exception:
                pass
    if 'last_seen_in_scan_id' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('last_seen_in_scan_id', sa.String(36), nullable=True)
            )
            # Add foreign key for last_seen_in_scan_id
            if not is_sqlite:
                try:
                    op.create_foreign_key(
                        'fk_findings_last_seen_in_scan_id',
                        'findings', 'scan_jobs',
                        ['last_seen_in_scan_id'], ['id']
                    )
                except Exception:
                    pass
        except Exception:
            pass
    if 'found_count' not in existing_columns:
        try:
            op.add_column('findings', 
                sa.Column('found_count', sa.Integer(), nullable=False, server_default='1')
            )
        except Exception:
            pass
    if 'not_seen_in_latest_scan' not in existing_columns:
        try:
            # For SQLite, use INTEGER with default 0/1; for PostgreSQL use BOOLEAN
            if is_sqlite:
                op.add_column('findings', 
                    sa.Column('not_seen_in_latest_scan', sa.Integer(), nullable=False, server_default='0')
                )
            else:
                op.add_column('findings', 
                    sa.Column('not_seen_in_latest_scan', sa.Boolean(), nullable=False, server_default='false')
                )
        except Exception:
            pass
    
    # Add remediation fields if they don't exist
    for col_name, col_type in [
        ('remediation_summary', sa.Text),
        ('remediation_steps', sa.Text),
        ('framework_hint', sa.String(100)),
    ]:
        if col_name not in existing_columns:
            try:
                op.add_column('findings', 
                    sa.Column(col_name, col_type(), nullable=True)
                )
            except Exception:
                pass
    
    # Backfill existing data: set project_id from scan_jobs, set lifecycle fields
    if not is_sqlite:
        # PostgreSQL
        op.execute(text("""
            UPDATE findings
            SET project_id = (
                SELECT project_id FROM scan_jobs WHERE scan_jobs.id = findings.scan_job_id
            ),
            first_seen_at = created_at,
            last_seen_at = created_at,
            last_seen_in_scan_id = scan_job_id,
            found_count = 1,
            tool = tool_name
            WHERE project_id IS NULL
        """))
    else:
        # SQLite
        op.execute(text("""
            UPDATE findings
            SET project_id = (
                SELECT project_id FROM scan_jobs WHERE scan_jobs.id = findings.scan_job_id
            ),
            first_seen_at = created_at,
            last_seen_at = created_at,
            last_seen_in_scan_id = scan_job_id,
            found_count = 1,
            tool = tool_name
            WHERE project_id IS NULL
        """))

def downgrade():
    # Drop indexes and columns in reverse order
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Drop remediation fields
    try:
        op.drop_column('findings', 'framework_hint')
        op.drop_column('findings', 'remediation_steps')
        op.drop_column('findings', 'remediation_summary')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise
    
    # Drop lifecycle fields
    try:
        op.drop_column('findings', 'not_seen_in_latest_scan')
        op.drop_column('findings', 'found_count')
        if not is_sqlite:
            op.drop_foreign_key('fk_findings_last_seen_in_scan_id', 'findings')
        op.drop_column('findings', 'last_seen_in_scan_id')
        op.drop_column('findings', 'last_seen_at')
        op.drop_column('findings', 'first_seen_at')
        op.drop_index('ix_findings_dedup_key', table_name='findings')
        op.drop_column('findings', 'dedup_key')
    except Exception as e:
        if 'no such column' not in str(e).lower() and 'no such index' not in str(e).lower():
            raise
    
    # Drop evidence field
    try:
        op.drop_column('findings', 'evidence')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise
    
    # Drop location fields
    try:
        op.drop_column('findings', 'cookie_name')
        op.drop_column('findings', 'header_name')
        op.drop_column('findings', 'parameter')
        op.drop_column('findings', 'http_method')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise
    
    # Drop vuln_type and category
    try:
        op.drop_column('findings', 'category')
        op.drop_index('ix_findings_vuln_type', table_name='findings')
        op.drop_column('findings', 'vuln_type')
    except Exception as e:
        if 'no such column' not in str(e).lower() and 'no such index' not in str(e).lower():
            raise
    
    # Drop template_id and rule_id
    try:
        op.drop_column('findings', 'rule_id')
        op.drop_index('ix_findings_template_id', table_name='findings')
        op.drop_column('findings', 'template_id')
    except Exception as e:
        if 'no such column' not in str(e).lower() and 'no such index' not in str(e).lower():
            raise
    
    # Drop tool column
    try:
        op.drop_index('ix_findings_tool', table_name='findings')
        op.drop_column('findings', 'tool')
    except Exception as e:
        if 'no such column' not in str(e).lower() and 'no such index' not in str(e).lower():
            raise
    
    # Drop project_id
    try:
        if not is_sqlite:
            op.drop_foreign_key('fk_findings_project_id', 'findings')
        op.drop_index('ix_findings_project_id', table_name='findings')
        op.drop_column('findings', 'project_id')
    except Exception as e:
        if 'no such column' not in str(e).lower() and 'no such index' not in str(e).lower():
            raise

