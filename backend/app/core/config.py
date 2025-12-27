"""
Core configuration settings for Thandev v2
"""
import os
from typing import Optional, Set, Tuple
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
    load_dotenv(env_path, override=False)  # do not override real environment variables
else:
    # Fallback: try current directory
    load_dotenv(override=False)

try:
    from pydantic_settings import BaseSettings
    from pydantic import ConfigDict, PrivateAttr
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
    _superadmin_external_ids_set: Set[Tuple[str, str]] = PrivateAttr(default_factory=set)
    
    # Database
    # CANONICAL ENV VAR: DATABASE_URL (used by both app runtime and Alembic migrations)
    # Default to SQLite for local/development, Postgres for production/docker/testing
    # For local development: uses SQLite by default (sqlite:///./thandev.db)
    # For production/docker/testing: set DATABASE_URL=postgresql://user:pass@host:port/db in .env
    # Or set ENVIRONMENT=production to default to Postgres
    # Note: migrations/env.py uses settings.DATABASE_URL, ensuring consistency
    DATABASE_URL: str = "sqlite:///./thandev.db"  # Default to SQLite for development (overridden in __init__ if needed)
    
    # Redis
    # Default to 6380 to avoid conflict with host Redis on 6379
    # Can be overridden via REDIS_URL environment variable
    REDIS_URL: str = "redis://localhost:6380/0"
    
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
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,https://thandev.com,https://thandev.vercel.app"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Tenant Auto-creation Configuration
    # Default: enabled in dev/test/local, disabled in production
    # Can be overridden with THANDEV_TENANT_AUTOCREATE=1 (only effective in non-production)
    # For production, requires additional flag: THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD=1
    TENANT_AUTOCREATE_ENABLED: bool = True  # Will be computed in __init__
    THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD: bool = False  # Extra safety guard for production
    
    # OpenAI (for AI planner and report generation)
    OPENAI_API_KEY: Optional[str] = None
    
    # Brain Service (for RAG-powered planning and report prompts)
    BRAIN_SERVICE_URL: str = "http://localhost:8001"
    BRAIN_SERVICE_ENABLED: bool = True  # Set to False to disable brain service and use fallback
    BRAIN_REQUIRED: bool = False  # If True, fail scan if brain is unreachable. Set to False to allow fallback
    BRAIN_SERVICE_TIMEOUT: int = 30  # Timeout in seconds for brain service requests
    
    # Scan Execution Path Configuration
    USE_CELERY_SCAN_EXECUTION: bool = False  # If True, use Celery for scan execution (legacy). Default: False (use Runner via Redis streams)
    
    # Scan Execution Configuration
    MAX_PARALLEL_TOOLS: int = 5  # Maximum number of tools to run in parallel
    MAX_SCAN_TIMEOUT_SECONDS: int = 3600  # Maximum total scan time (1 hour)
    TOOL_EXECUTION_TIMEOUT_SECONDS: int = 900  # Default timeout for individual tool execution (15 minutes)
    HTTP_PROBE_TIMEOUT_SECONDS: int = 10  # Timeout for HTTP probes during stack info collection
    
    # Findings Configuration
    MAX_INDIVIDUAL_FINDINGS_PER_SCAN: int = 300  # Maximum individual findings to ingest per scan
    HIGH_RISK_PORTS: str = "22,3389,5900"  # Comma-separated list of high-risk ports (SSH, RDP, VNC)
    
    # Scan Recovery Configuration
    SCAN_RECOVERY_MODE: str = "requeue"  # How to handle stale scans: "requeue" (resume) or "fail" (cancel)
    SCAN_RECOVERY_MAX_STALE_AGE_HOURS: int = 24  # Maximum age in hours for a scan to be considered stale
    SCAN_RECOVERY_ENABLED: bool = False  # Enable scan recovery on startup (disabled by default to avoid false positives)
    
    # Stalled Scan Detection
    STALLED_SCAN_THRESHOLD_MINUTES: int = 30  # Minutes a scan can be RUNNING without progress before marked STALLED
    STALLED_SCAN_NO_PROGRESS_POLLS: int = 3  # Number of consecutive polls with no progress change before marking STALLED

    # Self-service signup (GitHub bootstrap)
    SELF_SERVICE_SIGNUP_ENABLED: bool = True  # Computed in __init__

    # Domain verification / staging safety
    DOMAIN_VERIFICATION_DISABLED: bool = False
    ALLOWED_SCAN_DOMAINS: str = ""  # Comma-separated registrable domains for staging/demo

    # Admin bootstrap (legacy email/id) — prefer SUPERADMIN_EXTERNAL_IDS for security
    THANDEV_ADMIN_EMAILS: Optional[str] = None  # comma-separated
    THANDEV_ADMIN_GITHUB_IDS: Optional[str] = None  # comma-separated
    # Deterministic superadmin list: "provider:external_id" (e.g., github:123456)
    THANDEV_SUPERADMIN_EXTERNAL_IDS: Optional[str] = None
    # One-time setup token for first superadmin
    THANDEV_SETUP_TOKEN: Optional[str] = None
    
    model_config = ConfigDict(
        # Use absolute path to .env file to ensure it's found even when running from different directories
        env_file=str(env_path) if env_path.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Convert CORS_ORIGINS string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_scan_domains(self) -> list[str]:
        """Registrable domains allowed (staging/demo)"""
        if not self.ALLOWED_SCAN_DOMAINS:
            return []
        return [d.strip().lower() for d in self.ALLOWED_SCAN_DOMAINS.split(",") if d.strip()]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Override DATABASE_URL default based on ENVIRONMENT if not explicitly set in env
        if "DATABASE_URL" not in os.environ:
            env_lower = self.ENVIRONMENT.lower()
            # Use Postgres for all environments except explicit SQLite override
            # This ensures consistency between backend and runner
            if env_lower in ("production", "docker", "testing", "staging", "local", "dev", "development"):
                self.DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/thandev"
            # Only use SQLite if explicitly set or in a special test mode
        
        # Set Celery URLs to Redis URL if not specified
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        
        # Compute TENANT_AUTOCREATE_ENABLED based on environment and env vars
        env_lower = self.ENVIRONMENT.strip().lower()
        is_production = env_lower == "production"
        is_dev_env = env_lower in ("local", "dev", "test", "development")
        
        # Check explicit override from env var
        explicit_autocreate = os.getenv("THANDEV_TENANT_AUTOCREATE", "").strip() == "1"
        dangerous_prod_flag = os.getenv("THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD", "").strip() == "1"
        
        if is_production:
            # In production: disabled by default, only enabled if dangerous flag is set
            self.TENANT_AUTOCREATE_ENABLED = dangerous_prod_flag
        elif is_dev_env:
            # In dev/test/local: enabled by default, can be disabled with explicit flag
            self.TENANT_AUTOCREATE_ENABLED = explicit_autocreate if explicit_autocreate else True
        else:
            # Other environments: respect explicit flag, default to False for safety
            self.TENANT_AUTOCREATE_ENABLED = explicit_autocreate

        # Compute SELF_SERVICE_SIGNUP_ENABLED
        explicit_self_service = os.getenv("SELF_SERVICE_SIGNUP_ENABLED")
        if explicit_self_service is not None:
            self.SELF_SERVICE_SIGNUP_ENABLED = explicit_self_service.strip() in ("1", "true", "True", "TRUE")
        else:
            # Default: disabled in production, enabled elsewhere
            self.SELF_SERVICE_SIGNUP_ENABLED = not is_production

        # Parse superadmin external IDs once at startup
        superadmin_set: set[tuple[str, str]] = set()
        raw_superadmins = os.getenv("THANDEV_SUPERADMIN_EXTERNAL_IDS", "") or (self.THANDEV_SUPERADMIN_EXTERNAL_IDS or "")
        for item in raw_superadmins.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" not in item:
                # Ignore malformed entries quietly
                continue
            provider, external_id = item.split(":", 1)
            provider = provider.strip().lower()
            external_id = external_id.strip()
            if provider and external_id:
                superadmin_set.add((provider, external_id))
        object.__setattr__(self, "_superadmin_external_ids_set", superadmin_set)

    @property
    def superadmin_external_ids_set(self) -> Set[Tuple[str, str]]:
        return set(self._superadmin_external_ids_set)

    def set_superadmin_external_ids(self, pairs: Set[Tuple[str, str]]):
        """Test/helper hook to override superadmin set safely."""
        object.__setattr__(self, "_superadmin_external_ids_set", set(pairs))


settings = Settings()

