"""
Configuration settings for Thandev Runner Service
"""
from pydantic_settings import BaseSettings
from typing import ClassVar
import os
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings"""
    
    # Service configuration
    PROJECT_NAME: str = "Thandev Runner Service"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Database Configuration (for findings ingestion)
    # CRITICAL: Runner must use the SAME DATABASE_URL as backend to avoid "scan job not found" errors
    # Default to SQLite for development, Postgres for production
    # For local development, set DATABASE_URL=sqlite:///.../backend/thandev.db in .env
    # For production/docker/testing, set DATABASE_URL=postgresql://user:pass@host:port/db
    # 
    # IMPORTANT: If DATABASE_URL is not set, try to match backend's default behavior:
    # - Backend defaults to postgresql://postgres:postgres@localhost:5432/thandev in local/dev/production
    DATABASE_URL: str = ""  # Will be computed in __init__
    
    # Consumer Configuration
    CONSUMER_GROUP: str = os.getenv("CONSUMER_GROUP", "runner-workers")
    CONSUMER_NAME: str = os.getenv("CONSUMER_NAME", os.getenv("HOSTNAME", "runner-1"))
    
    # Execution Configuration
    EXECUTION_ADAPTER: str = os.getenv("EXECUTION_ADAPTER", "local")  # local or remote
    MAX_CONCURRENT_STEPS: int = int(os.getenv("MAX_CONCURRENT_STEPS", "20"))
    MAX_INFLIGHT_PER_SESSION: int = int(os.getenv("MAX_INFLIGHT_PER_SESSION", "100"))
    
    # Tool Execution paths (computed in __init__)
    TOOLS_BASE_DIR: str = ""
    DATA_DIR: str = ""
    JOBS_DIR: str = ""
    WORDLISTS_DIR: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Environment variables take precedence over .env file
        env_ignore_empty = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Compute repo root
        _repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # Compute DATABASE_URL if not explicitly set
        # CRITICAL: Runner must use the SAME database as backend to avoid "scan job not found" errors
        # Backend defaults to PostgreSQL, so runner should too
        # ALWAYS check environment variable first (set by start script) - it takes precedence over .env file
        env_db_url = os.getenv("DATABASE_URL")
        if env_db_url:
            # Environment variable takes precedence - override any .env file value
            self.DATABASE_URL = env_db_url
            logger.info(f"Using DATABASE_URL from environment (overrides .env): {self.DATABASE_URL}")
        elif not self.DATABASE_URL or self.DATABASE_URL == "":
            _default_postgres_url = "postgresql://postgres:postgres@localhost:5432/thandev"
            # Always default to PostgreSQL to match backend
            self.DATABASE_URL = _default_postgres_url
            logger.info(f"Using default PostgreSQL database: {self.DATABASE_URL}")
        else:
            logger.info(f"Using DATABASE_URL from .env file: {self.DATABASE_URL}")
        
        # Compute tool execution paths if not set
        if not self.TOOLS_BASE_DIR:
            self.TOOLS_BASE_DIR = os.getenv("TOOLS_BASE_DIR", os.path.join(_repo_root, "backend"))
        if not self.DATA_DIR:
            self.DATA_DIR = os.getenv("DATA_DIR", os.path.join(_repo_root, "backend", "data"))
        if not self.JOBS_DIR:
            self.JOBS_DIR = os.getenv("JOBS_DIR", os.path.join(self.DATA_DIR, "jobs"))
        if not self.WORDLISTS_DIR:
            self.WORDLISTS_DIR = os.getenv("WORDLISTS_DIR", os.path.join(_repo_root, "wordlists"))


settings = Settings()
