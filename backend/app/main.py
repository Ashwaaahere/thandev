"""
Thandev v2 - Main FastAPI application
"""
import os
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from dotenv import load_dotenv

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import ProgrammingError

from app.core.config import settings
from app.core.database import engine, Base
from app.api import projects, scans, tenants, users, metrics, findings, performance, notifications, admin, access
from app.api import findings_batch
from app.api import auth_bootstrap
from app.api import domain_verifications
from app.api import stats
from app.api import runner_ingest
from app.api import integrations
from app.api import runner_callback

# Load environment variables
load_dotenv()

# Configure logging
# Use JSON logging in production, human-readable in development
USE_JSON_LOGGING = os.getenv("USE_JSON_LOGGING", "false").lower() == "true"
if USE_JSON_LOGGING:
    from app.core.logging_config import setup_structured_logging
    setup_structured_logging(use_json=True)
else:
    logging.basicConfig(
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("Starting Thandev v2 API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")
    logger.info(f"Redis: {settings.REDIS_URL.split('@')[-1] if '@' in settings.REDIS_URL else 'configured'}")
    
    # Log Alembic version and database schema for debugging migration issues
    try:
        from sqlalchemy import text
        startup_logger = logging.getLogger(__name__)
        
        # Log DATABASE_URL (redacted password) - show hostname/dbname for verification
        db_url_parsed = urlparse(settings.DATABASE_URL)
        # Log only hostname, port, and database name (mask username and password)
        db_url_display = f"{db_url_parsed.scheme}://***:***@{db_url_parsed.hostname}:{db_url_parsed.port or 'default'}{db_url_parsed.path}"
        startup_logger.info(f"Runtime DATABASE_URL: {db_url_display}")
        
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                )
            """))
            table_exists = result.scalar()
            
            if table_exists:
                result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                current_version = result.scalar()
                logger.info(f"Alembic DB version: {current_version}")
            else:
                logger.warning("alembic_version table does not exist - migrations may not have run")
            
            # Get expected head revision
            try:
                from alembic.config import Config
                from alembic.script import ScriptDirectory
                alembic_cfg = Config("alembic.ini")
                script = ScriptDirectory.from_config(alembic_cfg)
                head_revision = script.get_current_head()
                logger.info(f"Alembic expected head: {head_revision}")
                if table_exists and current_version != head_revision:
                    logger.warning(
                        f"Alembic version mismatch! DB has {current_version}, "
                        f"expected {head_revision}. Run 'alembic upgrade head'"
                    )
            except Exception as e:
                logger.debug(f"Could not determine Alembic head revision: {e}")
            
            # Log actual columns in scan_jobs table (one-time diagnostic)
            try:
                columns_result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'scan_jobs'
                    ORDER BY ordinal_position
                """))
                columns = columns_result.fetchall()
                if columns:
                    startup_logger.info(f"scan_jobs table columns ({len(columns)} total): {', '.join([col[0] for col in columns])}")
                    # Log critical columns specifically
                    column_names = {col[0] for col in columns}
                    critical_columns = ['celery_task_id', 'scan_level', 'stack_info', 'project_id', 'brain_session_id']
                    missing = [col for col in critical_columns if col not in column_names]
                    if missing:
                        startup_logger.warning(f"Missing critical columns in scan_jobs: {', '.join(missing)}")
                    else:
                        startup_logger.info("All critical columns present in scan_jobs table")
                else:
                    startup_logger.warning("scan_jobs table has no columns (table may not exist)")
            except Exception as e:
                startup_logger.warning(f"Could not check scan_jobs columns: {e}")
    except Exception as e:
        logger.warning(f"Could not check Alembic version: {e}")
    
    # Create database tables (in production, use Alembic migrations)
    # Only auto-create tables in development with SQLite
    # For Postgres, use Alembic migrations
    if settings.ENVIRONMENT == "development" and "sqlite" in settings.DATABASE_URL.lower():
        logger.info("Creating database tables (SQLite development mode)...")
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.warning(f"Could not create tables automatically: {e}. Use Alembic migrations instead.")
    elif settings.ENVIRONMENT == "development" and "postgresql" in settings.DATABASE_URL.lower():
        logger.info("Using Postgres in development - ensure migrations are run with: alembic upgrade head")
    
    # Recover stale scans from system downtime
    if settings.SCAN_RECOVERY_ENABLED:
        try:
            from app.services.scan_recovery import recover_scans_on_startup
            recover_scans_on_startup(
                recovery_mode=settings.SCAN_RECOVERY_MODE,
                max_stale_age_hours=settings.SCAN_RECOVERY_MAX_STALE_AGE_HOURS
            )
        except Exception as e:
            logger.error(f"Scan recovery failed during startup: {e}", exc_info=True)
            # Don't fail startup if recovery fails - log and continue
    else:
        logger.info("Scan recovery is disabled (SCAN_RECOVERY_ENABLED=false)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Thandev v2 API...")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Security intelligence platform API",
    lifespan=lifespan,
)

# CORS middleware
# In development, the Next.js frontend at http://localhost:3000 calls this FastAPI backend at :8000.
# In production, configure CORS_ORIGINS to allow your production frontend domain.
# Must explicitly include OPTIONS in allow_methods for preflight requests
# CORS middleware must be added BEFORE routers are included
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=["*"],  # Allow all headers for CORS preflight
)

# Response compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Internal endpoint security middleware
@app.middleware("http")
async def internal_endpoint_security(request: Request, call_next):
    """
    Protect /api/internal/* endpoints from public access.
    
    Note: Runner endpoints have been moved to /api/runner/* to avoid Fly.io proxy blocking.
    They still require Bearer token authentication via require_runner_service_auth.
    
    In production, these endpoints should only be accessible from:
    - Private networks (RFC1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Allowed IP addresses/CIDR blocks (INTERNAL_ENDPOINT_ALLOWED_IPS)
    - Or behind an internal load balancer/gateway
    
    Note: Bearer token authentication is still required via require_runner_service_auth.
    This middleware adds an additional layer of network-level protection.
    """
    if request.url.path.startswith("/api/internal/"):
        from app.core.config import settings
        import ipaddress
        
        # Get client IP (check X-Forwarded-For for proxies, fallback to direct)
        client_ip_str = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip_str:
            client_ip_str = request.client.host if request.client else None
        
        if not client_ip_str:
            logger.warning("Internal endpoint accessed without identifiable client IP")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "Internal endpoint access denied"}
            )
        
        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            logger.warning(f"Invalid client IP format: {client_ip_str}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "Internal endpoint access denied"}
            )
        
        # Check if IP is allowed
        allowed = False
        
        # Option 0: Always allow if Bearer token is present (will be validated by dependency)
        # This allows Fly.io internal networking while maintaining security via token auth
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            allowed = True
            logger.debug(f"Internal endpoint accessed with Bearer token from {client_ip_str}, allowing")
        
        # Option 1: Fly.io internal network (IPv6 range fdaa::/48)
        if not allowed:
            try:
                # Fly.io uses fdaa::/48 for internal networking
                fly_internal_network = ipaddress.ip_network("fdaa::/48")
                if isinstance(client_ip, ipaddress.IPv6Address) and client_ip in fly_internal_network:
                    allowed = True
                    logger.debug(f"Internal endpoint accessed from Fly.io internal network {client_ip_str}")
            except Exception:
                pass
        
        # Option 2: Require private network (RFC1918)
        if not allowed and settings.INTERNAL_ENDPOINT_REQUIRE_PRIVATE_NETWORK:
            private_networks = [
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("127.0.0.0/8"),  # localhost
            ]
            allowed = any(client_ip in net for net in private_networks)
        
        # Option 3: Check allowed IPs/CIDR blocks
        if not allowed and settings.INTERNAL_ENDPOINT_ALLOWED_IPS:
            allowed_ips = [ip.strip() for ip in settings.INTERNAL_ENDPOINT_ALLOWED_IPS.split(",") if ip.strip()]
            for allowed_ip_str in allowed_ips:
                if allowed_ip_str.lower() == "private":
                    # RFC1918 private networks
                    private_networks = [
                        ipaddress.ip_network("10.0.0.0/8"),
                        ipaddress.ip_network("172.16.0.0/12"),
                        ipaddress.ip_network("192.168.0.0/16"),
                        ipaddress.ip_network("127.0.0.0/8"),
                    ]
                    if any(client_ip in net for net in private_networks):
                        allowed = True
                        break
                else:
                    try:
                        allowed_net = ipaddress.ip_network(allowed_ip_str)
                        if client_ip in allowed_net:
                            allowed = True
                            break
                    except ValueError:
                        logger.warning(f"Invalid allowed IP format: {allowed_ip_str}")
        
        # In development, allow all if no restrictions configured
        if not allowed and settings.ENVIRONMENT == "development" and not settings.INTERNAL_ENDPOINT_REQUIRE_PRIVATE_NETWORK and not settings.INTERNAL_ENDPOINT_ALLOWED_IPS:
            allowed = True
            logger.debug(f"Development mode: allowing internal endpoint access from {client_ip_str}")
        
        if not allowed:
            logger.warning(
                f"Internal endpoint access denied from {client_ip_str} (path: {request.url.path})"
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "Internal endpoint access denied"}
            )
    
    return await call_next(request)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    import time
    start_time = time.time()
    
    logger.info(f"{request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Check if response was actually returned
        if response is None:
            logger.error(f"No response returned for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "No response returned from route handler"
                }
            )
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response
    except RuntimeError as e:
        if "No response returned" in str(e):
            logger.error(f"No response returned for {request.method} {request.url.path}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "Route handler did not return a response"
                }
            )
        raise


# Database ProgrammingError handler (catch schema mismatches)
@app.exception_handler(ProgrammingError)
async def database_programming_error_handler(request: Request, exc: ProgrammingError):
    """
    Catch database ProgrammingError (like UndefinedColumn) and return clear error message.
    This prevents 500 errors from schema mismatches from crashing the entire request.
    """
    try:
        from psycopg2.errors import UndefinedColumn
        # Check if it's an UndefinedColumn error
        orig = getattr(exc, 'orig', None)
        if orig and isinstance(orig, UndefinedColumn):
            error_detail = str(orig)
            logger.error(
                f"Database schema mismatch: {error_detail}. "
                f"Request: {request.method} {request.url.path}. "
                f"Run 'alembic upgrade head' to update database schema."
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Database schema error",
                    "message": "The database schema is out of sync with the application code. "
                              "Please contact support or run database migrations.",
                    "detail": "A required database column is missing. This usually indicates "
                             "that migrations need to be run."
                }
            )
    except ImportError:
        # psycopg2 not available, can't check for UndefinedColumn
        pass
    
    # For other ProgrammingErrors, log and return generic error
    logger.error(f"Database ProgrammingError: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Database error",
            "message": "A database error occurred. Please contact support."
        }
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        }
    )


# Health check endpoint
@app.get("/health")
@app.get("/healthz")  # Alternative health endpoint for Fly.io and other platforms
async def health():
    """Health check endpoint - returns service status"""
    return {
        "status": "ok",
        "service": "thandev-backend",
        "version": settings.VERSION,
    }


# Readiness check endpoint
@app.get("/ready")
async def ready():
    """
    Readiness check endpoint - verifies critical dependencies are available.
    Returns 200 if ready, 500 if not ready.
    """
    checks = {}
    all_ready = True
    
    # Check database
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = "ready"
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        checks["database"] = f"not_ready: {str(e)}"
        all_ready = False
    
    # Check Redis
    try:
        import os
        import redis
        from urllib.parse import urlparse
        parsed = urlparse(settings.REDIS_URL)
        use_tls = parsed.scheme == "rediss"
        redis_kwargs = {"socket_connect_timeout": 2, "decode_responses": True}
        if use_tls:
            redis_kwargs["ssl"] = True
            if os.getenv("REDIS_TLS_INSECURE", "").lower() in ("true", "1", "yes"):
                import ssl
                redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
                redis_kwargs["ssl_check_hostname"] = False
        redis_client = redis.from_url(settings.REDIS_URL, **redis_kwargs)
        redis_client.ping()
        checks["redis"] = "ready"
    except Exception as e:
        logger.error(f"Redis readiness check failed: {e}")
        checks["redis"] = f"not_ready: {str(e)}"
        all_ready = False
    
    # Check Qdrant (if brain service is enabled and uses Qdrant)
    # Note: This is optional - brain service may use pgvector instead
    if settings.BRAIN_SERVICE_ENABLED:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                brain_url = settings.BRAIN_URL if settings.BRAIN_URL else settings.BRAIN_SERVICE_URL
                response = await client.get(f"{brain_url}/health")
                if response.status_code == 200:
                    checks["brain_service"] = "ready"
                else:
                    checks["brain_service"] = f"not_ready: HTTP {response.status_code}"
                    all_ready = False
        except Exception as e:
            logger.warning(f"Brain service readiness check failed (may be optional): {e}")
            checks["brain_service"] = f"not_ready: {str(e)}"
            # Don't fail readiness if brain service is optional
    
    status_code = 200 if all_ready else 500
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
            "version": settings.VERSION,
        }
    )


# Include API routers
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(scans.router, prefix=settings.API_V1_PREFIX)
app.include_router(tenants.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(metrics.router, prefix=settings.API_V1_PREFIX)
app.include_router(findings.router, prefix=settings.API_V1_PREFIX)
app.include_router(findings_batch.router, prefix=settings.API_V1_PREFIX)
app.include_router(performance.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_bootstrap.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(access.router, prefix=settings.API_V1_PREFIX)
app.include_router(domain_verifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(stats.router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations.router, prefix=settings.API_V1_PREFIX)
# Runner service endpoints - moved from /api/internal to /api/runner to avoid Fly.io proxy blocking
# Still requires Bearer token authentication via require_runner_service_auth
app.include_router(runner_ingest.router, prefix="/api/runner")
app.include_router(runner_callback.router, prefix="/api")


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Security intelligence platform API",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
