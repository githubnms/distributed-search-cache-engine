"""
Locust Load Testing Script
Tests system performance under concurrent load
"""

from locust import HttpUser, task, between, events
import random
import json
from datetime import datetime
import logging

# Test queries
SEARCH_QUERIES = [
    "artificial intelligence",
    "machine learning",
    "redis cache",
    "distributed systems",
    "database optimization",
    "python programming",
    "fastapi tutorial",
    "docker containers",
    "kubernetes cluster",
    "microservices architecture"
]

# Test documents for upload
TEST_DOCUMENTS = [
    {
        "title": "Load Test Document 1",
        "content": "This is a test document for load testing purposes. " * 50,
        "author": "Load Tester",
        "tags": ["test", "load-testing", "performance"]
    }
]

class SearchUser(HttpUser):
    """
    Simulates a user performing search operations
    """
    wait_time = between(0.5, 2)  # Wait between 0.5-2 seconds between tasks
    
    def on_start(self):
        """Initialize user session"""
        self.session_id = f"session-{random.randint(1000, 9999)}"
        self.search_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        print(f"User {self.session_id} started")
    
    @task(5)
    def search(self):
        """Perform search queries"""
        query = random.choice(SEARCH_QUERIES)
        
        with self.client.get(
            f"/api/v1/search/?q={query}&limit=10",
            catch_response=True,
            name="/search"
        ) as response:
            
            if response.status_code == 200:
                data = response.json()
                self.search_count += 1
                
                if data.get('cache_hit', False):
                    self.cache_hits += 1
                else:
                    self.cache_misses += 1
                
                # Track performance
                events.request.fire(
                    request_type="SEARCH",
                    name=query,
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    context={
                        "cache_hit": data.get('cache_hit', False),
                        "result_count": data.get('total_results', 0)
                    }
                )
                
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(1)
    def get_stats(self):
        """Get system statistics"""
        with self.client.get(
            "/api/v1/stats/",
            catch_response=True,
            name="/stats"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stats failed: {response.status_code}")
    
    @task(1)
    def get_popular(self):
        """Get popular queries"""
        with self.client.get(
            "/api/v1/search/popular",
            catch_response=True,
            name="/popular"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Popular failed: {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Check system health"""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    def on_stop(self):
        """Log user session stats"""
        hit_rate = (self.cache_hits / self.search_count * 100) if self.search_count > 0 else 0
        print(f"User {self.session_id} completed - Searches: {self.search_count}, Cache Hit Rate: {hit_rate:.1f}%")

class DocumentUser(HttpUser):
    """
    Simulates a user performing document operations
    """
    wait_time = between(1, 3)
    
    @task(1)
    def upload_document(self):
        """Upload a test document"""
        doc = random.choice(TEST_DOCUMENTS)
        
        with self.client.post(
            "/api/v1/documents/",
            json=doc,
            catch_response=True,
            name="/upload"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task(3)
    def list_documents(self):
        """List documents"""
        with self.client.get(
            "/api/v1/documents/?limit=20",
            catch_response=True,
            name="/documents"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List failed: {response.status_code}")

class MixedUser(HttpUser):
    """
    Simulates mixed workload (search + document operations)
    """
    wait_time = between(0.3, 1.5)
    
    @task(10)
    def search(self):
        """Search operation"""
        query = random.choice(SEARCH_QUERIES)
        with self.client.get(
            f"/api/v1/search/?q={query}",
            catch_response=True,
            name="/search_mixed"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(2)
    def get_document(self):
        """Get specific document (assuming some exist)"""
        doc_id = random.randint(1, 100)
        with self.client.get(
            f"/api/v1/documents/{doc_id}",
            catch_response=True,
            name="/documents/{id}"
        ) as response:
            if response.status_code in [200, 404]:
                # 404 is acceptable for random IDs
                response.success()
            else:
                response.failure(f"Get document failed: {response.status_code}")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("=" * 60)
    print("🚀 LOAD TEST STARTING")
    print(f"Host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count}")
    print(f"Spawn rate: {environment.runner.spawn_rate} users/sec")
    print("=" * 60)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("=" * 60)
    print("📊 LOAD TEST COMPLETE")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")
    print(f"Avg response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {environment.stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"Requests/sec: {environment.stats.total.current_rps:.2f}")
    print("=" * 60)

# Custom shape class for staged load testing
class StagedLoadShape:
    """
    Custom load shape for staged testing
    Stages: Warmup -> Steady -> Spike -> Cooldown
    """
    
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 2},    # Warmup
        {"duration": 120, "users": 50, "spawn_rate": 5},   # Light load
        {"duration": 180, "users": 100, "spawn_rate": 10}, # Medium load
        {"duration": 120, "users": 200, "spawn_rate": 20}, # Heavy load
        {"duration": 60, "users": 500, "spawn_rate": 50},  # Peak load
        {"duration": 60, "users": 100, "spawn_rate": 20},  # Cooldown
    ]
    
    def tick(self):
        """Return (user_count, spawn_rate) for current time"""
        run_time = self.get_run_time()
        
        total_duration = 0
        for stage in self.stages:
            if run_time < total_duration + stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            total_duration += stage["duration"]
        
        return None