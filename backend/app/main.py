"""
Thandev v2 - Main FastAPI application
"""
import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.core.database import engine, Base
from app.api import projects, scans, tenants, users, metrics, findings, performance, notifications, admin, access
from app.api import findings_batch
from app.api import auth_bootstrap
from app.api import domain_verifications

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


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
