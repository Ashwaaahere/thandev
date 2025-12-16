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
        rag_store = get_rag_store()
        if hasattr(rag_store, 'initialize'):
            await rag_store.initialize()
            logger.info("RAG store initialized")
    except Exception as e:
        logger.warning(f"RAG store initialization skipped: {e}")
    
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
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "thandev-brain",
        "version": "1.0.0",
    }


# Include API routers
app.include_router(v1_router, prefix="/v1")
# RAG router is included in v1_router, so it's available at /v1/rag/*

