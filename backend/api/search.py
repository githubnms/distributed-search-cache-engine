"""
Search API Routes
Handles search requests and query processing
"""

from fastapi import APIRouter, HTTPException, Request, Query
import time
import logging
from typing import Optional, List, Dict, Any

from ..services.search_service import SearchService
from ..services.cache_service import CacheService
from ..services.analytics_service import AnalyticsService
from ..utils.rate_limiter import RateLimiter

router = APIRouter(prefix="/api/v1/search", tags=["search"])
logger = logging.getLogger(__name__)

# Initialize services
search_service = SearchService()
cache_service = CacheService()
analytics_service = AnalyticsService()
rate_limiter = RateLimiter()

@router.get("/")
async def search(
    request: Request,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Number of results to return", ge=1, le=100),
    offset: int = Query(0, description="Pagination offset", ge=0)
):
    """
    Search for documents matching the query
    
    Args:
        q: Search query string
        limit: Maximum number of results
        offset: Pagination offset
        
    Returns:
        Search results with metadata
    """
    start_time = time.time()
    cache_hit = False
    
    try:
        # Check rate limit
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.allow_request(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return {
                "query": q,
                "total_results": 0,
                "execution_time_ms": 0,
                "cache_hit": False,
                "results": [],
                "error": "Rate limit exceeded. Please try again later."
            }
        
        # Check cache first
        cached_results = await cache_service.get_cached_results(q)
        
        if cached_results:
            logger.info(f"Cache hit for query: {q}")
            cache_hit = True
            results = cached_results
        else:
            logger.info(f"Cache miss for query: {q}")
            # Perform search
            results = await search_service.search(q, limit + offset)
            
            # Apply pagination
            paginated_results = results[offset:offset + limit] if results else []
            
            # Cache results if any
            if paginated_results:
                await cache_service.cache_results(q, paginated_results)
            
            results = paginated_results
        
        execution_time = (time.time() - start_time) * 1000
        
        # Track analytics (don't await to avoid blocking)
        import asyncio
        asyncio.create_task(
            analytics_service.track_search(
                query=q,
                execution_time_ms=execution_time,
                cache_hit=cache_hit,
                result_count=len(results),
                user_agent=request.headers.get("user-agent"),
                ip_address=client_ip
            )
        )
        
        # Format results for response
        formatted_results = []
        for doc in results:
            if hasattr(doc, 'to_dict'):
                formatted_results.append(doc.to_dict())
            else:
                # Handle if doc is already a dict
                formatted_results.append(doc)
        
        return {
            "query": q,
            "total_results": len(results),
            "execution_time_ms": round(execution_time, 2),
            "cache_hit": cache_hit,
            "results": formatted_results
        }
        
    except Exception as e:
        logger.error(f"Search error for query '{q}': {str(e)}", exc_info=True)
        # Return empty results instead of throwing error
        return {
            "query": q,
            "total_results": 0,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "cache_hit": False,
            "results": [],
            "error": str(e)
        }

@router.get("/popular")
async def get_popular_queries(
    period: str = Query("24h", description="Time period (e.g., 24h, 7d)"),
    limit: int = Query(10, description="Number of results", ge=1, le=50)
):
    """
    Get most popular search queries
    """
    try:
        popular = await analytics_service.get_popular_queries(period, limit)
        return {"queries": popular}
    except Exception as e:
        logger.error(f"Error getting popular queries: {e}")
        return {"queries": []}

@router.get("/suggest")
async def get_suggestions(
    q: str = Query(..., description="Partial query for suggestions"),
    limit: int = Query(5, description="Number of suggestions", ge=1, le=10)
):
    """
    Get search suggestions based on partial query
    """
    try:
        if len(q) < 2:
            return {"suggestions": []}
        
        suggestions = await search_service.get_suggestions(q, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return {"suggestions": []}