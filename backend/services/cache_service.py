"""
Cache Service Module
Handles Redis caching operations
"""

import redis
import pickle
import json
from typing import Optional, Any, List, Dict
import logging
import time
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service"""
    
    def __init__(self):
        self.redis_client = None
        self.stats = {
            'hits': 0,
            'misses': 0,
            'popular_queries': {}
        }
        self._connect()
    
    def _connect(self):
        """Establish connection to Redis"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Connected to Redis successfully")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None
    
    async def get_cached_results(self, query: str) -> Optional[List]:
        """Get cached search results"""
        try:
            if not self.redis_client:
                return None
            
            # Try to get from cache
            cached = self.redis_client.get(f"search:{query}")
            
            if cached:
                self.stats['hits'] += 1
                # Update popularity
                self._update_popularity(query)
                logger.debug(f"Cache hit for query: {query}")
                return pickle.loads(cached)
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss for query: {query}")
                return None
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats['misses'] += 1
            return None
    
    async def cache_results(self, query: str, results: List, ttl: int = None):
        """Cache search results"""
        try:
            if not self.redis_client:
                return
            
            if ttl is None:
                ttl = settings.CACHE_TTL
            
            # Cache the results
            self.redis_client.setex(
                f"search:{query}",
                ttl,
                pickle.dumps(results)
            )
            
            logger.info(f"Cached query '{query}' with TTL {ttl}s")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def _update_popularity(self, query: str):
        """Update query popularity counter"""
        try:
            if not self.redis_client:
                return
            
            # Increment popularity counter in a sorted set
            self.redis_client.zincrby("popular_queries", 1, query)
            self.redis_client.expire("popular_queries", 86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Popularity update error: {e}")
    
    async def get_popular_queries(self, limit: int = 10) -> List[Dict]:
        """Get most popular queries"""
        try:
            if not self.redis_client:
                return []
            
            # Get top queries from sorted set
            popular = self.redis_client.zrevrange(
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
    
    async def clear_cache(self, pattern: str = "*") -> int:
        """Clear cache entries matching pattern"""
        try:
            if not self.redis_client:
                return 0
            
            keys = self.redis_client.keys(f"search:{pattern}")
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    async def get_cache_statistics(self) -> Dict:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': round(hit_rate, 3),
            'total_requests': total
        }
    
    async def get_detailed_stats(self) -> Dict:
        """Get detailed cache statistics"""
        try:
            if not self.redis_client:
                return self.stats
            
            # Get Redis info
            info = self.redis_client.info()
            
            stats = await self.get_cache_statistics()
            stats.update({
                'redis_version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_keys': len(self.redis_client.keys('*'))
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting detailed stats: {e}")
            return self.stats
    
    async def record_hit(self):
        """Record a cache hit"""
        self.stats['hits'] += 1
    
    async def record_miss(self):
        """Record a cache miss"""
        self.stats['misses'] += 1
    
    async def health_check(self) -> bool:
        """Check Redis health"""
        try:
            if not self.redis_client:
                return False
            
            self.redis_client.ping()
            return True
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False