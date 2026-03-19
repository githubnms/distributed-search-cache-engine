"""
Main Application Module
Production-ready FastAPI application with metrics and monitoring
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import time
import os
import psutil
from typing import Dict
import asyncio
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client import multiprocess

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

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
ACTIVE_REQUESTS = Gauge('http_requests_active', 'Active HTTP requests')
CACHE_HITS = Counter('cache_hits_total', 'Total cache hits')
CACHE_MISSES = Counter('cache_misses_total', 'Total cache misses')
SEARCH_COUNT = Counter('search_operations_total', 'Total search operations')
DOCUMENT_COUNT = Gauge('documents_total', 'Total number of documents')
SYSTEM_MEMORY = Gauge('system_memory_usage_bytes', 'System memory usage')
SYSTEM_CPU = Gauge('system_cpu_usage_percent', 'System CPU usage')

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("="*80)
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION} in {settings.ENVIRONMENT} mode")
    logger.info(f"📊 Workers: {os.getenv('WORKERS', '1')}")
    logger.info(f"🔄 Redis: {settings.REDIS_URL}")
    logger.info(f"🗄️ Database: {settings.DATABASE_URL}")
    logger.info("="*80)
    
    # Start background tasks
    asyncio.create_task(collect_system_metrics())
    
    # Check Redis connection
    redis_healthy = await cache_service.health_check()
    if redis_healthy:
        redis_info = await cache_service.get_detailed_stats()
        logger.info(f"✅ Redis connected - Version: {redis_info.get('redis_version', 'unknown')}")
        logger.info(f"📈 Redis memory: {redis_info.get('used_memory_human', 'unknown')}")
    else:
        logger.warning("⚠️ Redis not available - running without cache")
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down application...")
    
    # Close connections
    try:
        db.close_all_connections()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")
    
    try:
        if hasattr(cache_service, 'redis_client') and cache_service.redis_client:
            cache_service.redis_client.close()
            logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis: {e}")
    
    logger.info("👋 Application shutdown complete")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    Distributed Search & Cache Engine (DSCE)
    
    A production-ready, scalable search system with:
    * 🔍 Full-text search with inverted indexing
    * ⚡ Distributed Redis caching with automatic failover
    * 📊 Real-time analytics and monitoring
    * 🚀 High throughput with async processing
    * 📈 Prometheus metrics integration
    * 🔄 Horizontal scaling support
    """,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    contact={
        "name": "DSCE Team",
        "url": "https://github.com/yourusername/distributed-search-cache-engine",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    }
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.ENVIRONMENT == "development" else ["localhost", "127.0.0.1", "yourdomain.com"]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect metrics for each request"""
    ACTIVE_REQUESTS.inc()
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    ACTIVE_REQUESTS.dec()
    
    return response

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()
    request_id = f"{time.time()}-{id(request)}"
    
    logger.info(f"📥 Request [{request_id}] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        logger.info(
            f"📤 Response [{request_id}] {response.status_code} - {duration*1000:.2f}ms"
        )
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration*1000:.2f}ms"
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error [{request_id}] {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id
            }
        )

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting"""
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        from .utils.rate_limiter import rate_limiter
        
        if not await rate_limiter.allow_request(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
    
    return await call_next(request)

# Include routers
app.include_router(search.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")

# Health check endpoint
@app.get("/health")
async def health_check() -> Dict:
    """Detailed health check"""
    redis_healthy = await cache_service.health_check()
    
    # Check database
    db_healthy = False
    db_latency = 0
    try:
        start = time.time()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_latency = (time.time() - start) * 1000
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    return {
        "status": "healthy" if (redis_healthy and db_healthy) else "degraded",
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime": time.time() - start_time,
        "services": {
            "api": {
                "status": "healthy",
                "latency_ms": 0
            },
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "latency_ms": round(db_latency, 2),
                "path": db.db_path if hasattr(db, 'db_path') else 'unknown'
            },
            "redis": {
                "status": "healthy" if redis_healthy else "unhealthy",
                "latency_ms": 0
            }
        },
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024)
        }
    }

# Root endpoint
@app.get("/")
async def root() -> Dict:
    """API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Production-ready Distributed Search & Cache Engine",
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "search": "/api/v1/search/?q={query}",
            "documents": "/api/v1/documents/",
            "stats": "/api/v1/stats/",
            "health": "/health",
            "metrics": "/metrics"
        },
        "features": [
            "Distributed Redis caching with replication",
            "High availability with Redis Sentinel",
            "PostgreSQL with connection pooling",
            "Prometheus metrics integration",
            "Rate limiting (1000 req/min)",
            "Gzip compression",
            "Horizontal scaling support",
            "Real-time analytics"
        ],
        "status": "operational"
    }

# Background tasks
async def collect_system_metrics():
    """Collect system metrics periodically"""
    while True:
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            SYSTEM_CPU.set(cpu_percent)
            SYSTEM_MEMORY.set(memory.used)
            
            # Document count
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM documents")
                count = cursor.fetchone()[0]
                DOCUMENT_COUNT.set(count)
            
            await asyncio.sleep(15)  # Collect every 15 seconds
            
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            await asyncio.sleep(30)

# Store start time for uptime calculation
start_time = time.time()

# Serve frontend
try:
    if os.path.exists("frontend"):
        app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
        logger.info("✅ Frontend static files mounted")
    else:
        logger.warning("⚠️ Frontend directory not found")
except Exception as e:
    logger.error(f"❌ Failed to mount frontend: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        workers=int(os.getenv("WORKERS", 4)),
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*"
    )