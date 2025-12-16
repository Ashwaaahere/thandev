"""
Database session management for runner service
"""
import logging
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
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )
        logger.info(f"Created database engine for {settings.DATABASE_URL}")
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



