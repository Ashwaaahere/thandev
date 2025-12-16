"""
Core configuration settings for Thandev v2
"""
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before Settings is instantiated
# This ensures .env is loaded even when running from different directories (e.g., Celery workers)
# Find backend directory: go up from app/core/config.py to backend/
# __file__ is at: backend/app/core/config.py
# .parent = backend/app/core/
# .parent.parent = backend/app/
# .parent.parent.parent = backend/
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # Fallback: try current directory
    load_dotenv(override=True)

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # pydantic-settings is required for pydantic >= 2.0
    # If not installed, provide a clear error message
    raise ImportError(
        "pydantic-settings package is required but not installed. "
        "Please install it with: pip install pydantic-settings\n"
        "Or install all requirements: pip install -r requirements.txt"
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = "sqlite:///./thandev.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    
    # API
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Thandev v2"
    VERSION: str = "2.0.0"
    
    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    # For development, allow localhost:3000 (Next.js frontend) to call this backend
    # Also allow 127.0.0.1:3000 in case browser resolves localhost differently
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,https://thandev.com"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # OpenAI (for AI planner and report generation)
    OPENAI_API_KEY: Optional[str] = None
    
    # Brain Service (for RAG-powered planning and report prompts)
    BRAIN_SERVICE_URL: str = "http://localhost:8001"
    BRAIN_SERVICE_ENABLED: bool = True  # Set to False to disable brain service and use fallback
    BRAIN_REQUIRED: bool = True  # If True, fail scan if brain is unreachable (PR-1 requirement)
    
    class Config:
        # Use absolute path to .env file to ensure it's found even when running from different directories
        env_file = str(env_path) if env_path.exists() else ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Convert CORS_ORIGINS string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set Celery URLs to Redis URL if not specified
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL


settings = Settings()

