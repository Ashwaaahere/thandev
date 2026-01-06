"""add ai_plan and ai_status to scan_jobs

Revision ID: 0005_add_ai_plan_fields
Revises: 0004_add_timed_out
Create Date: 2025-12-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0005_add_ai_plan_fields'
down_revision = '0004_add_timed_out'
branch_labels = None
depends_on = None

def upgrade():
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Add ai_plan column (JSON)
    try:
        if is_sqlite:
            # SQLite uses TEXT for JSON
            op.add_column('scan_jobs', 
                sa.Column('ai_plan', sa.Text(), nullable=True)
            )
        else:
            # PostgreSQL uses JSONB
            op.add_column('scan_jobs',
                sa.Column('ai_plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
            )
    except Exception as e:
        if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
            raise
    
    # Add ai_status column (ENUM)
    try:
        # Create enum type for PostgreSQL
        if not is_sqlite:
            # Check if enum type already exists
            from sqlalchemy import text
            result = bind.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'aistatus')"
            )).scalar()
            
            if not result:
                op.execute("CREATE TYPE aistatus AS ENUM ('idle', 'planned', 'failed')")
        
        # Add column
        if is_sqlite:
            # SQLite uses TEXT for enum
            op.add_column('scan_jobs',
                sa.Column('ai_status', sa.String(20), nullable=True, server_default='idle')
            )
        else:
            # PostgreSQL uses enum type
            op.add_column('scan_jobs',
                sa.Column('ai_status', postgresql.ENUM('idle', 'planned', 'failed', name='aistatus'), nullable=True, server_default='idle')
            )
    except Exception as e:
        if 'duplicate column' not in str(e).lower() and 'already exists' not in str(e).lower():
            raise

def downgrade():
    # Remove ai_status column
    try:
        op.drop_column('scan_jobs', 'ai_status')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise
    
    # Remove ai_plan column
    try:
        op.drop_column('scan_jobs', 'ai_plan')
    except Exception as e:
        if 'no such column' not in str(e).lower():
            raise
    
    # Drop enum type for PostgreSQL (if it exists and no other columns use it)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    if not is_sqlite:
        try:
            from sqlalchemy import text
            # Check if any other columns use this enum
            result = bind.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE udt_name = 'aistatus'
            """)).scalar()
            
            if result == 0:
                op.execute("DROP TYPE IF EXISTS aistatus")
        except Exception:
            pass






