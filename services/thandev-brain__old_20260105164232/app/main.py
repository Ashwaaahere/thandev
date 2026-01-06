"""
Thandev Brain Service
RAG-powered planning and report prompt generation for security scans
"""
import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1 import router as v1_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("Starting Thandev Brain Service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize RAG store if needed
    try:
        from app.rag.store import get_rag_store
        # settings already imported at top of file
        logger.info(f"Initializing RAG store (type: {settings.RAG_STORE_TYPE}, url: {settings.QDRANT_URL})")
        rag_store = get_rag_store()
        if hasattr(rag_store, 'initialize'):
            await rag_store.initialize()
            logger.info("✅ RAG store initialized successfully")
        else:
            logger.warning("RAG store does not have initialize method")
    except Exception as e:
        logger.error(f"⚠️ RAG store initialization failed (will retry on first use): {e}", exc_info=True)
        # Don't fail startup - collection will be created on first query if needed
    
    yield
    
    # Shutdown
    logger.info("Shutting down Thandev Brain Service...")


# Create FastAPI app
app = FastAPI(
    title="Thandev Brain Service",
    version="1.0.0",
    description="RAG-powered scan planning and report prompt generation",
    lifespan=lifespan,
)

# CORS middleware
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
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        return response
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(e),
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
async def health():
    """Health check endpoint - returns service status"""
    return {
        "status": "ok",
        "service": "thandev-brain",
        "version": "1.0.0",
    }


@app.get("/healthz")
async def healthz():
    """Health check endpoint (alias for /health)"""
    return {
        "status": "ok",
        "service": "thandev-brain",
        "version": "1.0.0",
    }


# Readiness check endpoint
@app.get("/ready")
async def ready():
    """
    Readiness check endpoint - verifies critical dependencies are available.
    Returns 200 if ready, 500 if not ready.
    """
    from fastapi.responses import JSONResponse
    checks = {}
    all_ready = True
    
    # Check RAG store
    try:
        from app.rag.store import get_rag_store
        rag_store = get_rag_store()
        
        if settings.RAG_STORE_TYPE == "qdrant":
            # Check Qdrant connection
            try:
                # Try to get collections to verify connection
                if hasattr(rag_store, '_client') and rag_store._client:
                    collections = rag_store._client.get_collections()
                    checks["qdrant"] = "ready"
                else:
                    # Client not initialized, try to initialize
                    await rag_store.initialize()
                    if hasattr(rag_store, '_client') and rag_store._client:
                        checks["qdrant"] = "ready"
                    else:
                        checks["qdrant"] = "not_ready: client not initialized"
                        all_ready = False
            except Exception as e:
                logger.error(f"Qdrant readiness check failed: {e}")
                checks["qdrant"] = f"not_ready: {str(e)}"
                all_ready = False
        elif settings.RAG_STORE_TYPE == "pgvector":
            # Check PostgreSQL connection (for pgvector)
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(settings.DATABASE_URL)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                checks["postgresql"] = "ready"
            except Exception as e:
                logger.error(f"PostgreSQL readiness check failed: {e}")
                checks["postgresql"] = f"not_ready: {str(e)}"
                all_ready = False
        else:
            checks["rag_store"] = f"not_ready: unknown store type {settings.RAG_STORE_TYPE}"
            all_ready = False
    except Exception as e:
        logger.error(f"RAG store readiness check failed: {e}")
        checks["rag_store"] = f"not_ready: {str(e)}"
        all_ready = False
    
    status_code = 200 if all_ready else 500
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
            "version": "1.0.0",
        }
    )


# Include API routers
app.include_router(v1_router, prefix="/v1")
# RAG router is included in v1_router, so it's available at /v1/rag/*

