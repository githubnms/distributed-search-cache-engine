"""
Main Application Module
Initializes FastAPI app, configures middleware, and includes routers
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import time
import os
from typing import Dict

from .config import settings
from .api import search, documents, stats
from .utils.logger import setup_logging, get_logger
from .database import db
from .services.cache_service import CacheService

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Initialize services
cache_service = CacheService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("="*60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("="*60)
    
    # Check Redis connection
    redis_healthy = await cache_service.health_check()
    if redis_healthy:
        logger.info("Redis cache is connected")
    else:
        logger.warning("Redis cache not available - running without caching")
    
    # Check database
    try:
        # Test database connection
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
        logger.info(f"Database connected at: {db.db_path}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Close database connections
    try:
        db.close_all_connections()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    # Close Redis connection
    try:
        if hasattr(cache_service, 'redis_client') and cache_service.redis_client:
            cache_service.redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
    logger.info("Application shutdown complete")

# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Distributed Search & Cache Engine (DSCE)
    
    A scalable search system demonstrating:
    * Full-text search with inverted indexing
    * Redis caching with adaptive TTL
    * Real-time analytics dashboard
    * Document management
    * Distributed systems concepts
    """,
    lifespan=lifespan,
    contact={
        "name": "DSCE Team",
        "url": "https://github.com/yourusername/distributed-search-cache-engine",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    }
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests
    """
    start_time = time.time()
    
    # Generate request ID
    request_id = f"{time.time()}-{id(request)}"
    
    # Log request
    logger.info(
        f"Request [{request_id}] - {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response [{request_id}] - Status: {response.status_code} - "
            f"Duration: {duration*1000:.2f}ms"
        )
        
        # Add response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration*1000:.2f}ms"
        
        return response
        
    except Exception as e:
        # Log error
        duration = time.time() - start_time
        logger.error(
            f"Error [{request_id}] - {str(e)} - Duration: {duration*1000:.2f}ms",
            exc_info=True
        )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id
            }
        )

# Error handling middleware
@app.middleware("http")
async def error_handler(request: Request, call_next):
    """
    Global error handling middleware
    """
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

# Include routers
app.include_router(search.router)
app.include_router(documents.router)
app.include_router(stats.router)

# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check() -> Dict:
    """
    Comprehensive health check endpoint
    
    Returns:
        Status of all services
    """
    # Check Redis
    redis_healthy = await cache_service.health_check()
    
    # Check database
    db_healthy = False
    db_path = "unknown"
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_healthy = True
        db_path = db.db_path
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Overall status
    all_healthy = redis_healthy and db_healthy
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": {
                "status": "healthy",
                "message": "API service is running"
            },
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "path": db_path,
                "message": "Connected" if db_healthy else "Connection failed"
            },
            "redis": {
                "status": "healthy" if redis_healthy else "unhealthy",
                "message": "Connected" if redis_healthy else "Not available - running without cache"
            }
        }
    }

# Root endpoint
@app.get("/", tags=["System"])
async def root() -> Dict:
    """
    Root endpoint with API information
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Distributed Search & Cache Engine",
        "environment": settings.ENVIRONMENT,
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "search": "/api/v1/search/?q={query}",
            "documents": "/api/v1/documents/",
            "stats": "/api/v1/stats/",
            "health": "/health"
        },
        "status": "running"
    }

# API information endpoint
@app.get("/api/v1/info", tags=["System"])
async def api_info() -> Dict:
    """
    Get detailed API information
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "features": [
            "Full-text search with inverted indexing",
            "Redis caching with adaptive TTL",
            "Real-time analytics dashboard",
            "Document management",
            "Distributed systems simulation",
            "Rate limiting",
            "Fault tolerance"
        ],
        "cache": {
            "type": "Redis",
            "ttl": f"{settings.CACHE_TTL}s",
            "status": "connected" if await cache_service.health_check() else "disconnected"
        },
        "database": {
            "type": "SQLite",
            "path": db.db_path,
            "size": os.path.getsize(db.db_path) if os.path.exists(db.db_path) else 0
        }
    }

# Serve favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return JSONResponse(content={})

# Serve frontend static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )