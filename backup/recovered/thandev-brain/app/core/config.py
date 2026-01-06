"""
Configuration settings for Thandev Brain Service
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Service configuration
    PROJECT_NAME: str = "Thandev Brain Service"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
    
    # RAG Configuration
    RAG_STORE_TYPE: str = os.getenv("RAG_STORE_TYPE", "qdrant")  # qdrant or pgvector
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://thandev-qdrant.flycast:6333")  # Use flycast for private networking
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "thandev_rag")
    
    # PostgreSQL (for pgvector)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/thandev")
    
    # Embedding Provider
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers")  # sentence_transformers or openai
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Brain Service Configuration
    BRAIN_MAX_STEPS: int = int(os.getenv("BRAIN_MAX_STEPS", "20"))
    BRAIN_MAX_PARALLELISM: int = int(os.getenv("BRAIN_MAX_PARALLELISM", "5"))
    BRAIN_MAX_TOTAL_RUNTIME_SEC: int = int(os.getenv("BRAIN_MAX_TOTAL_RUNTIME_SEC", "3600"))
    
    # Redis Configuration (for session state and queues)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SESSION_TTL_SEC: int = int(os.getenv("REDIS_SESSION_TTL_SEC", "86400"))  # 24 hours
    
    # Session Configuration
    SESSION_MAX_STEPS: int = int(os.getenv("SESSION_MAX_STEPS", "20"))
    SESSION_MAX_RUNTIME_SEC: int = int(os.getenv("SESSION_MAX_RUNTIME_SEC", "3600"))
    SESSION_MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("SESSION_MAX_CONSECUTIVE_FAILURES", "3"))
    SESSION_NO_NEW_FINDINGS_ITERATIONS: int = int(os.getenv("SESSION_NO_NEW_FINDINGS_ITERATIONS", "3"))
    
    # Finding Enrichment Configuration
    ENRICH_FINDINGS_ENABLED: bool = os.getenv("ENRICH_FINDINGS_ENABLED", "true").lower() == "true"
    ENRICH_FINDINGS_MODEL: str = os.getenv("ENRICH_FINDINGS_MODEL", "gpt-4o-mini")
    ENRICH_FINDINGS_TIMEOUT_SEC: int = int(os.getenv("ENRICH_FINDINGS_TIMEOUT_SEC", "30"))
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


