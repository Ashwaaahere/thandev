"""
Database session management for runner service
"""
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.config import settings

logger = logging.getLogger(__name__)

# Database engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine"""
    global _engine
    if _engine is None:
        # SQLite needs special connection args for multi-threaded access
        connect_args = {}
        database_url = settings.DATABASE_URL
        
        # Fix SQLite relative paths to absolute
        if database_url.startswith("sqlite:///./"):
            # Convert relative path to absolute
            from pathlib import Path
            repo_root = Path(__file__).parent.parent.parent.parent
            db_file = database_url.replace("sqlite:///./", "")
            absolute_path = repo_root / db_file
            database_url = f"sqlite:///{absolute_path}"
            logger.info(f"Converted relative SQLite path to absolute: {database_url}")
        elif database_url.startswith("sqlite:///"):
            # Ensure absolute path for SQLite
            db_path = database_url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                from pathlib import Path
                repo_root = Path(__file__).parent.parent.parent.parent
                absolute_path = repo_root / db_path
                database_url = f"sqlite:///{absolute_path}"
                logger.info(f"Converted relative SQLite path to absolute: {database_url}")
        
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        
        _engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True if not database_url.startswith("sqlite") else False,
            echo=settings.DEBUG,
        )
        logger.info(f"Created database engine for {database_url}")
    return _engine


def get_session_factory():
    """Get or create session factory"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db_session() -> Session:
    """
    Get a database session.
    
    Returns:
        SQLAlchemy Session instance
        
    Note: Caller is responsible for closing the session.
    """
    SessionLocal = get_session_factory()
    return SessionLocal()



