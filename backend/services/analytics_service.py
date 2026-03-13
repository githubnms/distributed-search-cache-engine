from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import logging
import statistics
from collections import defaultdict

from ..database import db
from ..models import AnalyticsEvent
from ..config import settings

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for tracking and analyzing search analytics"""
    
    def __init__(self):
        self.events_buffer = []
        self.buffer_size = 100
        self.performance_metrics = {
            'response_times': [],
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    async def track_search(self, query: str, execution_time_ms: float, 
                          cache_hit: bool, result_count: int,
                          user_agent: Optional[str] = None,
                          ip_address: Optional[str] = None):
        """Track a search event"""
        event = AnalyticsEvent(
            query=query,
            execution_time_ms=execution_time_ms,
            cache_hit=cache_hit,
            result_count=result_count,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        # Add to buffer
        self.events_buffer.append(event)
        
        # Update performance metrics
        self.performance_metrics['response_times'].append(execution_time_ms)
        if cache_hit:
            self.performance_metrics['cache_hits'] += 1
        else:
            self.performance_metrics['cache_misses'] += 1
        
        # Keep only last 1000 response times
        if len(self.performance_metrics['response_times']) > 1000:
            self.performance_metrics['response_times'] = \
                self.performance_metrics['response_times'][-1000:]
        
        # Flush buffer if needed
        if len(self.events_buffer) >= self.buffer_size:
            await self._flush_events()
        
        # Save to database asynchronously
        await self._save_event(event)
    
    async def _save_event(self, event: AnalyticsEvent):
        """Save event to database"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO search_analytics 
                    (query, timestamp, execution_time_ms, cache_hit, result_count, user_agent, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.query,
                    event.timestamp.isoformat(),
                    event.execution_time_ms,
                    event.cache_hit,
                    event.result_count,
                    event.user_agent,
                    event.ip_address
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving analytics event: {e}")
    
    async def _flush_events(self):
        """Flush events buffer to database"""
        if not self.events_buffer:
            return
        
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for event in self.events_buffer:
                    cursor.execute('''
                        INSERT INTO search_analytics 
                        (query, timestamp, execution_time_ms, cache_hit, result_count, user_agent, ip_address)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        event.query,
                        event.timestamp.isoformat(),
                        event.execution_time_ms,
                        event.cache_hit,
                        event.result_count,
                        event.user_agent,
                        event.ip_address
                    ))
                conn.commit()
            
            self.events_buffer.clear()
            logger.info(f"Flushed {len(self.events_buffer)} events to database")
            
        except Exception as e:
            logger.error(f"Error flushing events: {e}")
    
    async def get_search_statistics(self) -> Dict:
        """Get comprehensive search statistics"""
        stats = {
            'total_searches': 0,
            'unique_queries': 0,
            'avg_response_time': 0,
            'p95_response_time': 0,
            'p99_response_time': 0,
            'top_queries': []
        }
        
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total searches
                cursor.execute('SELECT COUNT(*) as count FROM search_analytics')
                stats['total_searches'] = cursor.fetchone()['count']
                
                # Unique queries
                cursor.execute('SELECT COUNT(DISTINCT query) as count FROM search_analytics')
                stats['unique_queries'] = cursor.fetchone()['count']
                
                # Average response time
                cursor.execute('SELECT AVG(execution_time_ms) as avg FROM search_analytics')
                stats['avg_response_time'] = round(cursor.fetchone()['avg'] or 0, 2)
                
                # Response time percentiles
                cursor.execute('SELECT execution_time_ms FROM search_analytics ORDER BY execution_time_ms')
                times = [row['execution_time_ms'] for row in cursor.fetchall()]
                
                if times:
                    times.sort()
                    p95_index = int(len(times) * 0.95)
                    p99_index = int(len(times) * 0.99)
                    
                    stats['p95_response_time'] = times[p95_index] if p95_index < len(times) else 0
                    stats['p99_response_time'] = times[p99_index] if p99_index < len(times) else 0
                
                # Top queries
                cursor.execute('''
                    SELECT query, COUNT(*) as count 
                    FROM search_analytics 
                    GROUP BY query 
                    ORDER BY count DESC 
                    LIMIT 10
                ''')
                
                stats['top_queries'] = [
                    {'query': row['query'], 'count': row['count']}
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error getting search statistics: {e}")
        
        return stats
    
    async def get_popular_queries(self, period: str = "24h", limit: int = 10) -> List:
        """Get popular queries for a time period"""
        try:
            # Calculate time threshold
            if period.endswith('h'):
                hours = int(period[:-1])
                threshold = datetime.utcnow() - timedelta(hours=hours)
            elif period.endswith('d'):
                days = int(period[:-1])
                threshold = datetime.utcnow() - timedelta(days=days)
            else:
                threshold = datetime.utcnow() - timedelta(days=1)
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT query, COUNT(*) as count 
                    FROM search_analytics 
                    WHERE timestamp > ? 
                    GROUP BY query 
                    ORDER BY count DESC 
                    LIMIT ?
                ''', (threshold.isoformat(), limit))
                
                return [
                    {'query': row['query'], 'count': row['count']}
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error getting popular queries: {e}")
            return []
    
    async def get_performance_metrics(self) -> Dict:
        """Get detailed performance metrics"""
        metrics = {
            'current': {},
            'historical': {},
            'trends': {}
        }
        
        try:
            # Current metrics from in-memory data
            if self.performance_metrics['response_times']:
                times = self.performance_metrics['response_times']
                metrics['current'] = {
                    'avg_response_time': round(statistics.mean(times), 2),
                    'median_response_time': round(statistics.median(times), 2),
                    'min_response_time': min(times),
                    'max_response_time': max(times),
                    'p95_response_time': sorted(times)[int(len(times) * 0.95)],
                    'cache_hit_rate': round(
                        self.performance_metrics['cache_hits'] / 
                        (self.performance_metrics['cache_hits'] + self.performance_metrics['cache_misses']),
                        3
                    ) if (self.performance_metrics['cache_hits'] + 
                          self.performance_metrics['cache_misses']) > 0 else 0
                }
            
            # Historical metrics from database
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Hourly breakdown for last 24 hours
                cursor.execute('''
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        COUNT(*) as searches,
                        AVG(execution_time_ms) as avg_time,
                        SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as hit_rate
                    FROM search_analytics
                    WHERE timestamp > datetime('now', '-24 hours')
                    GROUP BY hour
                    ORDER BY hour DESC
                ''')
                
                metrics['historical']['hourly'] = [
                    {
                        'hour': row['hour'],
                        'searches': row['searches'],
                        'avg_response_time': round(row['avg_time'], 2),
                        'cache_hit_rate': round(row['hit_rate'], 3)
                    }
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
        
        return metrics
    
    async def check_health(self) -> bool:
        """Check analytics service health"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM search_analytics LIMIT 1')
                return True
        except:
            return False