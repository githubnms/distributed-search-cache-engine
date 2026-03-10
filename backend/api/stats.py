from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from ..schemas import StatsResponse
from ..services.analytics_service import AnalyticsService
from ..services.cache_service import CacheService
from ..services.indexing_service import IndexingService
from ..utils.logger import get_logger

router = APIRouter(prefix="/api/v1/stats", tags=["statistics"])
logger = get_logger(__name__)

analytics_service = AnalyticsService()
cache_service = CacheService()
indexing_service = IndexingService()

@router.get("/", response_model=StatsResponse)
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
        stats = StatsResponse(
            total_searches=search_stats['total_searches'],
            unique_queries=search_stats['unique_queries'],
            cache_hit_rate=cache_stats['hit_rate'],
            avg_response_time_ms=search_stats['avg_response_time'],
            total_documents=index_stats['total_documents'],
            index_size_mb=index_stats['size_mb'],
            top_queries=search_stats['top_queries'],
            performance_metrics={
                'p95_response_time_ms': search_stats['p95_response_time'],
                'p99_response_time_ms': search_stats['p99_response_time'],
                'cache_hits': cache_stats['hits'],
                'cache_misses': cache_stats['misses'],
                'documents_per_shard': index_stats['documents_per_shard']
            }
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")

@router.get("/cache")
async def get_cache_stats():
    """
    Get detailed cache statistics
    """
    try:
        cache_stats = await cache_service.get_detailed_stats()
        return cache_stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving cache statistics")

@router.get("/performance")
async def get_performance_metrics():
    """
    Get detailed performance metrics
    """
    try:
        metrics = await analytics_service.get_performance_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving performance metrics")

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    services = {
        'database': await indexing_service.check_health(),
        'redis': await cache_service.check_health(),
        'worker': await analytics_service.check_health()
    }
    
    overall_health = all(services.values())
    
    return {
        'status': 'healthy' if overall_health else 'degraded',
        'services': services,
        'timestamp': datetime.utcnow().isoformat()
    }