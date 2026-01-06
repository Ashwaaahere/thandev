import os
import logging
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

# Use environment variable with SQLite fallback for local development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")

# Determine if we're using PostgreSQL or SQLite
is_postgresql = DATABASE_URL.startswith("postgresql")

# Connection pool configuration
pool_config = {
    "poolclass": QueuePool,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_pre_ping": True,  # Verify connections before using
    "pool_recycle": 3600,  # Recycle connections after 1 hour
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    "future": True,
}

# SQLite doesn't support all pool options
if not is_postgresql:
    pool_config.pop("pool_size")
    pool_config.pop("max_overflow")
    pool_config.pop("pool_recycle")

engine = create_engine(DATABASE_URL, **pool_config)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# Connection retry logic
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better performance"""
    if not is_postgresql:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

def get_db():
    """Dependency for getting database session with retry logic"""
    db = SessionLocal()
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            # Test connection
            db.execute(text("SELECT 1"))
            yield db
            break
        except (OperationalError, DisconnectionError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection failed, retrying... (attempt {attempt + 1}/{max_retries})")
                db.rollback()
                time.sleep(retry_delay * (attempt + 1))
                db = SessionLocal()
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                db.rollback()
                raise
        finally:
            if attempt == max_retries - 1:
                db.close()

@contextmanager
def get_db_context():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def check_database_health() -> dict:
    """Check database connection health"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            return {
                "status": "healthy",
                "database": "postgresql" if is_postgresql else "sqlite",
                "pool_size": pool_config.get("pool_size", "N/A"),
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
