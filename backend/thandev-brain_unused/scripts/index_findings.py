#!/usr/bin/env python3
"""
Script to index existing findings into RAG store
"""
import asyncio
import sys
import os
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.rag.store import get_rag_store
from app.rag.ingestion import ingest_findings_batch
from app.core.config import settings
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def index_findings_from_database(
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 1000,
):
    """
    Index findings from core backend database into RAG store.
    
    Args:
        org_id: Filter by organization ID
        project_id: Filter by project ID
        limit: Maximum number of findings to index
    """
    try:
        from sqlalchemy import create_engine, text
        
        database_url = settings.DATABASE_URL
        if not database_url:
            logger.error("DATABASE_URL not configured")
            logger.error("Please set DATABASE_URL in .env file or use --use-api flag")
            return
        
        # Support both PostgreSQL and SQLite
        is_postgresql = database_url.startswith("postgresql")
        is_sqlite = database_url.startswith("sqlite")
        
        if not (is_postgresql or is_sqlite):
            logger.error(f"DATABASE_URL must be PostgreSQL or SQLite, got: {database_url[:30]}...")
            return
        
        # Check if tables exist
        logger.info("Checking database connection and tables...")
        
        engine = create_engine(database_url)
        rag_store = get_rag_store()
        
        # Query findings - use named placeholders for both SQLite and PostgreSQL
        # SQLAlchemy text() works with :name for both databases
        query = """
            SELECT 
                f.id, f.title, f.description, f.severity, f.cve_id, f.cvss_score,
                f.url, f.tool_name, f.raw_data, f.created_at,
                sj.project_id, p.tenant_id as org_id, p.target_url as target
            FROM findings f
            JOIN scan_jobs sj ON f.scan_job_id = sj.id
            JOIN projects p ON sj.project_id = p.id
            WHERE 1=1
        """
        
        params = {}
        if org_id:
            query += " AND p.tenant_id = :org_id"
            params["org_id"] = org_id
        if project_id:
            query += " AND sj.project_id = :project_id"
            params["project_id"] = project_id
        
        query += " ORDER BY f.created_at DESC LIMIT :limit"
        params["limit"] = limit
        
        logger.info(f"Querying findings from database (limit: {limit}, type: {'SQLite' if is_sqlite else 'PostgreSQL'})...")
        
        with engine.connect() as conn:
            # SQLAlchemy text() supports :name placeholders for both SQLite and PostgreSQL
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            if not rows:
                logger.info("No findings found to index")
                return
            
            logger.info(f"Found {len(rows)} findings to index")
            
            # Convert to finding dicts
            findings = []
            for row in rows:
                # Parse raw_data if it's a JSON string
                raw_data = None
                if row[8]:  # raw_data
                    try:
                        import json
                        raw_data = json.loads(row[8]) if isinstance(row[8], str) else row[8]
                    except:
                        raw_data = None
                
                finding = {
                    "id": row[0],
                    "title": row[1] or "",
                    "description": row[2],
                    "severity": row[3] if row[3] else "info",
                    "cve_id": row[4],
                    "cvss_score": float(row[5]) if row[5] is not None else None,
                    "url": row[6],
                    "tool_id": row[7] or "unknown",
                    "tool_name": row[7] or "unknown",
                    "raw_data": raw_data,
                    "org_id": row[11],
                    "project_id": row[10],
                    "target": row[12],
                }
                findings.append(finding)
            
            # Index in batches
            batch_size = 100
            total_indexed = 0
            
            for i in range(0, len(findings), batch_size):
                batch = findings[i:i + batch_size]
                # ingest_findings_batch expects findings with org_id and project_id in the dict
                # and will extract them to pass to rag_store.upsert_documents
                await ingest_findings_batch(rag_store, batch)
                total_indexed += len(batch)
                logger.info(f"Indexed {total_indexed}/{len(findings)} findings...")
            
            logger.info(f"Successfully indexed {total_indexed} findings into RAG store")
            
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        if "psycopg" in str(e).lower():
            logger.error("Install with: pip install psycopg2-binary")
        elif "sqlalchemy" in str(e).lower():
            logger.error("Install with: pip install sqlalchemy")
        else:
            logger.error(f"Install missing dependency: {e}")
    except Exception as e:
        error_str = str(e)
        if "Connection refused" in error_str or "port 5432" in error_str:
            logger.error("PostgreSQL connection failed!")
            logger.error("Make sure PostgreSQL is running:")
            logger.error("  1. Check if PostgreSQL is running: sudo systemctl status postgresql")
            logger.error("  2. Or start it: sudo systemctl start postgresql")
            logger.error("  3. Or use Docker: docker-compose up -d postgres")
            logger.error("")
            logger.error("Alternatively, use the API method (if core backend is running):")
            logger.error("  python scripts/index_findings_api.py --limit 1000")
        elif "does not exist" in error_str or "UndefinedTable" in error_str:
            logger.error("Database tables don't exist!")
            logger.error("You need to run database migrations first:")
            logger.error("")
            logger.error("  1. Navigate to backend directory:")
            logger.error("     cd /home/shree/ashwath/thandev/backend")
            logger.error("")
            logger.error("  2. Run migrations:")
            logger.error("     alembic upgrade head")
            logger.error("")
            logger.error("  3. Or if using docker-compose:")
            logger.error("     docker-compose exec api alembic upgrade head")
            logger.error("")
            logger.error("This will create all required tables (findings, scan_jobs, projects, etc.)")
        else:
            logger.error(f"Failed to index findings: {e}", exc_info=True)
        raise


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Index findings into RAG store")
    parser.add_argument("--org-id", help="Filter by organization ID")
    parser.add_argument("--project-id", help="Filter by project ID")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum findings to index")
    
    args = parser.parse_args()
    
    await index_findings_from_database(
        org_id=args.org_id,
        project_id=args.project_id,
        limit=args.limit,
    )


if __name__ == "__main__":
    asyncio.run(main())

