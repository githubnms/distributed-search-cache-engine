"""
Statistics API Routes
Handles system statistics and monitoring
"""

from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime

from ..services.analytics_service import AnalyticsService
from ..services.cache_service import CacheService
from ..services.indexing_service import IndexingService

router = APIRouter(tags=["statistics"])
logger = logging.getLogger(__name__)

# Initialize services
analytics_service = AnalyticsService()
cache_service = CacheService()
indexing_service = IndexingService()

@router.get("/stats/")
async def get_statistics():
    """
    Get system statistics and performance metrics
    """
    try:
        # Gather statistics from all services
        search_stats = await analytics_service.get_search_statistics()
        cache_stats = await cache_service.get_cache_statistics()
        index_stats = await indexing_service.get_index_statistics()
        
        # Combine statistics
        stats = {
            "total_searches": search_stats.get('total_searches', 0),
            "unique_queries": search_stats.get('unique_queries', 0),
            "cache_hit_rate": cache_stats.get('hit_rate', 0),
            "avg_response_time_ms": search_stats.get('avg_response_time', 0),
            "total_documents": index_stats.get('total_documents', 0),
            "index_size_mb": index_stats.get('size_mb', 0),
            "top_queries": search_stats.get('top_queries', []),
            "performance_metrics": {
                "p95_response_time_ms": search_stats.get('p95_response_time', 0),
                "p99_response_time_ms": search_stats.get('p99_response_time', 0),
                "cache_hits": cache_stats.get('hits', 0),
                "cache_misses": cache_stats.get('misses', 0),
                "documents_per_shard": index_stats.get('documents_per_shard', {})
            }
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {
            "total_searches": 0,
            "unique_queries": 0,
            "cache_hit_rate": 0,
            "avg_response_time_ms": 0,
            "total_documents": 0,
            "index_size_mb": 0,
            "top_queries": [],
            "performance_metrics": {}
        }

@router.get("/stats/cache")
async def get_cache_stats():
    """
    Get detailed cache statistics
    """
    try:
        cache_stats = await cache_service.get_detailed_stats()
        return cache_stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}

@router.get("/stats/health")
async def health_check():
    """
    Health check for all services
    """
    services = {
        'database': await indexing_service.health_check(),
        'redis': await cache_service.health_check(),
        'analytics': await analytics_service.health_check()
    }
    
    overall_health = all(services.values())
    
    return {
        'status': 'healthy' if overall_health else 'degraded',
        'services': services,
        'timestamp': datetime.utcnow().isoformat()
    }