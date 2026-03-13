"""
Search Service Module
Handles search operations, caching, and result ranking
"""

from typing import List, Optional, Dict, Any
import logging
import time
from datetime import datetime

from ..models import Document
from ..services.indexing_service import IndexingService
from ..services.cache_service import CacheService
from ..services.ranking_service import RankingService
from ..utils.tokenizer import Tokenizer

logger = logging.getLogger(__name__)

class SearchService:
    """
    Service for handling search operations
    Implements caching, ranking, and query processing
    """
    
    def __init__(self):
        self.indexing_service = IndexingService()
        self.cache_service = CacheService()
        self.ranking_service = RankingService()
        self.tokenizer = Tokenizer()
        self.search_history = []
        
    async def search(self, query: str, limit: int = 10, offset: int = 0) -> List[Document]:
        """
        Perform search with caching and ranking
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of ranked Document objects
        """
        start_time = time.time()
        
        try:
            # Normalize query
            normalized_query = self._normalize_query(query)
            
            # Check cache first
            cached_results = await self.cache_service.get_cached_results(normalized_query)
            
            if cached_results:
                logger.info(f"Cache hit for query: '{query}'")
                # Update cache stats
                await self.cache_service.record_hit()
                results = cached_results
            else:
                logger.info(f"Cache miss for query: '{query}'")
                await self.cache_service.record_miss()
                
                # Perform search
                results = await self._execute_search(normalized_query)
                
                # Rank results
                results = await self.ranking_service.rank_results(results, normalized_query)
                
                # Cache results
                if results:
                    await self.cache_service.cache_results(normalized_query, results)
            
            # Apply pagination
            paginated_results = results[offset:offset + limit]
            
            # Record search history
            self._record_search(query, len(results), time.time() - start_time)
            
            logger.info(f"Search completed: '{query}' - {len(paginated_results)} results in {time.time()-start_time:.3f}s")
            return paginated_results
            
        except Exception as e:
            logger.error(f"Search error for query '{query}': {str(e)}")
            return []
    
    async def _execute_search(self, query: str) -> List[Document]:
        """
        Execute the actual search against the index
        
        Args:
            query: Normalized search query
            
        Returns:
            List of matching documents
        """
        try:
            # Tokenize query
            query_terms = self.tokenizer.tokenize(query)
            
            if not query_terms:
                return []
            
            # Get documents from index
            results = await self.indexing_service.search(query)
            
            # Add matched terms information
            for doc in results:
                matched_terms = []
                for term in query_terms:
                    if term in doc.content.lower():
                        matched_terms.append(term)
                doc.matched_terms = matched_terms
            
            return results
            
        except Exception as e:
            logger.error(f"Execute search error: {str(e)}")
            return []
    
    async def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """
        Get search suggestions based on partial query
        
        Args:
            query: Partial search query
            limit: Maximum number of suggestions
            
        Returns:
            List of suggestion strings
        """
        try:
            if len(query) < 2:
                return []
            
            suggestions = []
            
            # Get popular queries that match
            popular = await self.cache_service.get_popular_queries(10)
            for item in popular:
                if query.lower() in item['query'].lower():
                    suggestions.append(item['query'])
            
            # Add common completions
            common_suffixes = [' tutorial', ' guide', ' examples', ' best practices', ' documentation']
            for suffix in common_suffixes:
                suggestions.append(f"{query}{suffix}")
            
            # Remove duplicates and limit
            suggestions = list(dict.fromkeys(suggestions))[:limit]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Suggestions error: {str(e)}")
            return []
    
    async def get_search_analytics(self) -> Dict[str, Any]:
        """
        Get search analytics data
        
        Returns:
            Dictionary with search analytics
        """
        try:
            cache_stats = await self.cache_service.get_cache_statistics()
            
            # Calculate average response time
            if self.search_history:
                avg_time = sum(item['time'] for item in self.search_history) / len(self.search_history)
            else:
                avg_time = 0
            
            return {
                'total_searches': len(self.search_history),
                'average_response_time': round(avg_time * 1000, 2),  # Convert to ms
                'cache_hit_rate': cache_stats.get('hit_rate', 0),
                'popular_queries': await self.cache_service.get_popular_queries(10)
            }
            
        except Exception as e:
            logger.error(f"Search analytics error: {str(e)}")
            return {}
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize search query
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized query string
        """
        # Convert to lowercase
        normalized = query.lower().strip()
        
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _record_search(self, query: str, result_count: int, duration: float):
        """
        Record search in history
        
        Args:
            query: Search query
            result_count: Number of results
            duration: Search duration in seconds
        """
        self.search_history.append({
            'query': query,
            'result_count': result_count,
            'time': duration,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 1000 searches
        if len(self.search_history) > 1000:
            self.search_history = self.search_history[-1000:]
    
    async def clear_history(self):
        """Clear search history"""
        self.search_history = []
        logger.info("Search history cleared")
    
    async def health_check(self) -> bool:
        """
        Check service health
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check dependencies
            cache_healthy = await self.cache_service.health_check()
            index_healthy = await self.indexing_service.health_check()
            
            return cache_healthy and index_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False