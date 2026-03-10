from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
import time
import logging

from ..schemas import SearchRequest, SearchResponse, PopularQueriesResponse
from ..services.search_service import SearchService
from ..services.cache_service import CacheService
from ..services.analytics_service import AnalyticsService
from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter

router = APIRouter(prefix="/api/v1/search", tags=["search"])
logger = get_logger(__name__)

# Initialize services
search_service = SearchService()
cache_service = CacheService()
analytics_service = AnalyticsService()
rate_limiter = RateLimiter()

@router.get("/", response_model=SearchResponse)
async def search(
    request: Request,
    q: str,
    limit: Optional[int] = 10,
    offset: Optional[int] = 0
):
    """
    Search for documents matching the query
    """
    # Check rate limit
    client_ip = request.client.host
    if not rate_limiter.allow_request(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    start_time = time.time()
    cache_hit = False
    
    try:
        # Check cache first
        cached_results = await cache_service.get_cached_results(q)
        
        if cached_results:
            logger.info(f"Cache hit for query: {q}")
            cache_hit = True
            results = cached_results
            total_results = len(results)
        else:
            logger.info(f"Cache miss for query: {q}")
            # Perform search
            results = await search_service.search(q, limit, offset)
            total_results = len(results)
            
            # Cache results if any
            if results:
                await cache_service.cache_results(q, results, popularity=total_results)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Track analytics asynchronously
        await analytics_service.track_search(
            query=q,
            execution_time_ms=execution_time,
            cache_hit=cache_hit,
            result_count=total_results,
            user_agent=request.headers.get("user-agent"),
            ip_address=client_ip
        )
        
        return SearchResponse(
            query=q,
            total_results=total_results,
            execution_time_ms=execution_time,
            cache_hit=cache_hit,
            results=[r.to_dict() for r in results]
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal search error")

@router.get("/popular", response_model=PopularQueriesResponse)
async def get_popular_queries(
    period: str = "24h",
    limit: int = 10
):
    """
    Get most popular search queries
    """
    try:
        popular = await analytics_service.get_popular_queries(period, limit)
        return PopularQueriesResponse(
            period=period,
            queries=popular
        )
    except Exception as e:
        logger.error(f"Error fetching popular queries: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching popular queries")

@router.get("/suggest")
async def get_suggestions(q: str, limit: int = 5):
    """
    Get search suggestions based on partial query
    """
    try:
        suggestions = await search_service.get_suggestions(q, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        return {"suggestions": []}