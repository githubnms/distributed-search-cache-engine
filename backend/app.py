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
    description="Distributed Search & Cache Engine (DSCE)",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        f"Request [{request_id}] - {request.method} {request.url.path}"
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
        
        return response
        
    except Exception as e:
        # Log error
        duration = time.time() - start_time
        logger.error(
            f"Error [{request_id}] - {str(e)} - Duration: {duration*1000:.2f}ms"
        )
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

# Include routers - IMPORTANT: This mounts the API routes
app.include_router(search.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")

# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check() -> Dict:
    """
    Health check endpoint
    """
    # Check Redis
    redis_healthy = await cache_service.health_check()
    
    # Check database
    db_healthy = False
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    return {
        "status": "healthy" if (redis_healthy and db_healthy) else "degraded",
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": {"status": "healthy"},
            "database": {"status": "healthy" if db_healthy else "unhealthy"},
            "redis": {"status": "healthy" if redis_healthy else "unhealthy"}
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
        "endpoints": {
            "search": "/api/v1/search/?q={query}",
            "documents": "/api/v1/documents/",
            "stats": "/api/v1/stats/",
            "health": "/health",
            "docs": "/docs"
        },
        "status": "running"
    }

# Debug endpoint to list all routes (remove in production)
@app.get("/debug/routes", tags=["Debug"])
async def debug_routes():
    """List all registered routes (debug only)"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, 'methods') else None
        })
    return {"routes": routes}

# Serve frontend static files
try:
    # Check if frontend directory exists
    if os.path.exists("frontend"):
        app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
        logger.info("Frontend static files mounted from 'frontend' directory")
    else:
        logger.warning("Frontend directory not found - API only mode")
except Exception as e:
    logger.error(f"Failed to mount frontend: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )