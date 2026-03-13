"""
Rate Limiter Utility
Handles API rate limiting using token bucket algorithm
"""

import time
from collections import defaultdict
import logging
from typing import Dict, Tuple
import asyncio

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiter using token bucket algorithm
    """
    
    def __init__(self, default_requests: int = 60, default_period: int = 60):
        """
        Initialize rate limiter
        
        Args:
            default_requests: Default number of requests allowed
            default_period: Default time period in seconds
        """
        self.default_requests = default_requests
        self.default_period = default_period
        self.buckets: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        
    async def allow_request(self, client_id: str, requests: int = None, period: int = None) -> bool:
        """
        Check if request is allowed
        
        Args:
            client_id: Unique client identifier (IP, API key, etc.)
            requests: Number of requests allowed (overrides default)
            period: Time period in seconds (overrides default)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        async with self._lock:
            now = time.time()
            req_limit = requests or self.default_requests
            time_period = period or self.default_period
            
            # Get or create bucket for client
            if client_id not in self.buckets:
                self.buckets[client_id] = {
                    'tokens': req_limit,
                    'last_refill': now,
                    'limit': req_limit,
                    'period': time_period
                }
            
            bucket = self.buckets[client_id]
            
            # Refill tokens based on time elapsed
            time_passed = now - bucket['last_refill']
            refill_amount = time_passed * (bucket['limit'] / bucket['period'])
            
            bucket['tokens'] = min(bucket['limit'], bucket['tokens'] + refill_amount)
            bucket['last_refill'] = now
            
            # Check if token available
            if bucket['tokens'] >= 1:
                bucket['tokens'] -= 1
                return True
            else:
                logger.warning(f"Rate limit exceeded for {client_id}")
                return False
    
    async def get_remaining_tokens(self, client_id: str) -> Tuple[int, float]:
        """
        Get remaining tokens and reset time for a client
        
        Args:
            client_id: Client identifier
            
        Returns:
            Tuple of (remaining_tokens, seconds_until_reset)
        """
        if client_id not in self.buckets:
            return (self.default_requests, 0)
        
        bucket = self.buckets[client_id]
        now = time.time()
        
        # Calculate remaining tokens
        time_passed = now - bucket['last_refill']
        refill_amount = time_passed * (bucket['limit'] / bucket['period'])
        remaining = min(bucket['limit'], bucket['tokens'] + refill_amount)
        
        # Calculate time until full refill
        tokens_needed = bucket['limit'] - remaining
        seconds_until_reset = tokens_needed * (bucket['period'] / bucket['limit']) if tokens_needed > 0 else 0
        
        return (int(remaining), seconds_until_reset)
    
    async def reset_client(self, client_id: str):
        """
        Reset rate limit for a client
        
        Args:
            client_id: Client identifier
        """
        async with self._lock:
            if client_id in self.buckets:
                del self.buckets[client_id]
                logger.info(f"Rate limit reset for {client_id}")
    
    async def get_all_clients(self) -> Dict:
        """
        Get all clients and their rate limit status
        
        Returns:
            Dictionary of client statuses
        """
        result = {}
        for client_id, bucket in self.buckets.items():
            remaining, reset_in = await self.get_remaining_tokens(client_id)
            result[client_id] = {
                'remaining_tokens': remaining,
                'reset_in_seconds': reset_in,
                'limit': bucket['limit'],
                'period': bucket['period']
            }
        return result
    
    async def cleanup_old_clients(self, older_than_hours: int = 24):
        """
        Remove clients that haven't been active for a while
        
        Args:
            older_than_hours: Remove clients inactive for this many hours
        """
        async with self._lock:
            now = time.time()
            cutoff = now - (older_than_hours * 3600)
            
            to_delete = []
            for client_id, bucket in self.buckets.items():
                if bucket['last_refill'] < cutoff:
                    to_delete.append(client_id)
            
            for client_id in to_delete:
                del self.buckets[client_id]
            
            if to_delete:
                logger.info(f"Cleaned up {len(to_delete)} inactive clients")