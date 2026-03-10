import aioredis
import json
import pickle
from typing import Optional, Any, List
from datetime import datetime, timedelta
import logging
import asyncio

from ..config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service"""
    
    def __init__(self):
        self.redis = None
        self.stats = {
            'hits': 0,
            'misses': 0,
            'popular_queries': {}
        }
        self._connection_lock = asyncio.Lock()
    
    async def _get_connection(self):
        """Get Redis connection with lazy initialization"""
        if self.redis is None:
            async with self._connection_lock:
                if self.redis is None:
                    try:
                        self.redis = await aioredis.from_url(
                            settings.REDIS_URL,
                            max_connections=settings.REDIS_MAX_CONNECTIONS,
                            decode_responses=False
                        )
                        logger.info("Connected to Redis")
                    except Exception as e:
                        logger.error(f"Redis connection failed: {e}")
                        self.redis = None
        return self.redis
    
    async def get_cached_results(self, query: str) -> Optional[List]:
        """Get cached search results"""
        try:
            redis = await self._get_connection()
            if not redis:
                return None
            
            # Try to get from cache
            cached = await redis.get(f"search:{query}")
            
            if cached:
                self.stats['hits'] += 1
                # Update popularity
                await self._update_popularity(query)
                return pickle.loads(cached)
            else:
                self.stats['misses'] += 1
                return None
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats['misses'] += 1
            return None
    
    async def cache_results(self, query: str, results: List, popularity: int = 0):
        """Cache search results with adaptive TTL"""
        try:
            redis = await self._get_connection()
            if not redis:
                return
            
            # Calculate adaptive TTL based on popularity
            ttl = self._calculate_adaptive_ttl(query, popularity)
            
            # Cache the results
            await redis.setex(
                f"search:{query}",
                ttl,
                pickle.dumps(results)
            )
            
            logger.info(f"Cached query '{query}' with TTL {ttl}s")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def _calculate_adaptive_ttl(self, query: str, popularity: int) -> int:
        """Calculate adaptive TTL based on query popularity"""
        base_ttl = settings.CACHE_TTL
        
        # Check if query is popular
        popular_threshold = 10
        if popularity > 100:
            return base_ttl * 4
        elif popularity > 50:
            return base_ttl * 2
        elif popularity > popular_threshold:
            return base_ttl
        
        return base_ttl
    
    async def _update_popularity(self, query: str):
        """Update query popularity counter"""
        try:
            redis = await self._get_connection()
            if not redis:
                return
            
            # Increment popularity counter
            await redis.zincrby("popular_queries", 1, query)
            await redis.expire("popular_queries", 86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Popularity update error: {e}")
    
    async def get_popular_queries(self, limit: int = 10) -> List:
        """Get most popular queries"""
        try:
            redis = await self._get_connection()
            if not redis:
                return []
            
            # Get top queries from sorted set
            popular = await redis.zrevrange(
                "popular_queries",
                0,
                limit - 1,
                withscores=True
            )
            
            return [
                {"query": q.decode('utf-8'), "count": int(score)}
                for q, score in popular
            ]
            
        except Exception as e:
            logger.error(f"Error getting popular queries: {e}")
            return []
    
    async def clear_cache(self, pattern: str = "*"):
        """Clear cache entries matching pattern"""
        try:
            redis = await self._get_connection()
            if not redis:
                return 0
            
            keys = await redis.keys(f"search:{pattern}")
            if keys:
                deleted = await redis.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    async def get_cache_statistics(self) -> dict:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': round(hit_rate, 3),
            'total_requests': total
        }
    
    async def get_detailed_stats(self) -> dict:
        """Get detailed cache statistics"""
        try:
            redis = await self._get_connection()
            if not redis:
                return self.stats
            
            # Get Redis info
            info = await redis.info()
            
            stats = await self.get_cache_statistics()
            stats.update({
                'redis_version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_keys': await redis.dbsize()
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting detailed stats: {e}")
            return self.stats
    
    async def check_health(self) -> bool:
        """Check Redis health"""
        try:
            redis = await self._get_connection()
            if not redis:
                return False
            
            await redis.ping()
            return True
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False