"""
Configuration settings for Thandev Runner Service
"""
from pydantic_settings import BaseSettings
import os


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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
    
    # Consumer Configuration
    CONSUMER_GROUP: str = os.getenv("CONSUMER_GROUP", "runner-workers")
    CONSUMER_NAME: str = os.getenv("CONSUMER_NAME", os.getenv("HOSTNAME", "runner-1"))
    
    # Execution Configuration
    EXECUTION_ADAPTER: str = os.getenv("EXECUTION_ADAPTER", "local")  # local or remote
    MAX_CONCURRENT_STEPS: int = int(os.getenv("MAX_CONCURRENT_STEPS", "20"))
    MAX_INFLIGHT_PER_SESSION: int = int(os.getenv("MAX_INFLIGHT_PER_SESSION", "100"))
    
    # Tool Execution
    TOOLS_BASE_DIR: str = os.getenv("TOOLS_BASE_DIR", os.path.expanduser("~"))
    WORDLISTS_DIR: str = os.getenv("WORDLISTS_DIR", "/home/shree/ashwath/thandev/wordlists")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()



