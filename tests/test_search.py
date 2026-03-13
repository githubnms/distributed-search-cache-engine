import pytest
from fastapi.testclient import TestClient
import json
import time

from backend.app import app
from backend.database import db
from backend.services.cache_service import CacheService

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database"""
    # Clear database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM documents')
        cursor.execute('DELETE FROM inverted_index')
        cursor.execute('DELETE FROM search_analytics')
        conn.commit()
    
    # Add test documents
    test_docs = [
        {
            "title": "Test Document 1",
            "content": "This is a test document about artificial intelligence and machine learning.",
            "author": "Tester",
            "tags": ["test", "ai"]
        },
        {
            "title": "Test Document 2",
            "content": "Another test document about distributed systems and caching.",
            "author": "Tester",
            "tags": ["test", "distributed"]
        }
    ]
    
    for doc in test_docs:
        client.post("/api/v1/documents/", json=doc)
    
    yield

def test_search_basic():
    """Test basic search functionality"""
    response = client.get("/api/v1/search/?q=artificial+intelligence")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["query"] == "artificial intelligence"

def test_search_empty_query():
    """Test search with empty query"""
    response = client.get("/api/v1/search/?q=")
    assert response.status_code == 422  # Validation error

def test_search_pagination():
    """Test search with pagination"""
    response = client.get("/api/v1/search/?q=test&limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) <= 1

def test_cache_functionality():
    """Test caching mechanism"""
    query = "machine learning"
    
    # First request (cache miss)
    start_time = time.time()
    response1 = client.get(f"/api/v1/search/?q={query}")
    time1 = time.time() - start_time
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["cache_hit"] is False
    
    # Second request (cache hit)
    start_time = time.time()
    response2 = client.get(f"/api/v1/search/?q={query}")
    time2 = time.time() - start_time
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["cache_hit"] is True
    
    # Second request should be faster
    assert time2 < time1

def test_document_creation():
    """Test document creation"""
    new_doc = {
        "title": "New Test Document",
        "content": "This is a brand new test document.",
        "author": "Integration Tester",
        "tags": ["test", "integration"]
    }
    
    response = client.post("/api/v1/documents/", json=new_doc)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == new_doc["title"]
    assert data["author"] == new_doc["author"]
    assert "id" in data

def test_document_retrieval():
    """Test document retrieval by ID"""
    # First create a document
    new_doc = {
        "title": "Retrieval Test",
        "content": "Document for retrieval testing"
    }
    
    create_response = client.post("/api/v1/documents/", json=new_doc)
    doc_id = create_response.json()["id"]
    
    # Then retrieve it
    response = client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == new_doc["title"]

def test_document_deletion():
    """Test document deletion"""
    # Create document
    new_doc = {"title": "Delete Test", "content": "Document to delete"}
    create_response = client.post("/api/v1/documents/", json=new_doc)
    doc_id = create_response.json()["id"]
    
    # Delete it
    delete_response = client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_response.status_code == 200
    
    # Verify deletion
    get_response = client.get(f"/api/v1/documents/{doc_id}")
    assert get_response.status_code == 404

def test_statistics_endpoint():
    """Test statistics endpoint"""
    # Perform some searches
    client.get("/api/v1/search/?q=test")
    client.get("/api/v1/search/?q=test")
    client.get("/api/v1/search/?q=ai")
    
    # Get statistics
    response = client.get("/api/v1/stats/")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_searches" in data
    assert "cache_hit_rate" in data
    assert "top_queries" in data

def test_rate_limiting():
    """Test rate limiting"""
    # Make many requests quickly
    for i in range(10):
        response = client.get("/api/v1/search/?q=test")
        assert response.status_code == 200
    
    # Should hit rate limit eventually
    # Note: This depends on rate limit configuration

def test_batch_document_creation():
    """Test batch document creation"""
    batch_docs = {
        "documents": [
            {
                "title": "Batch Doc 1",
                "content": "First batch document"
            },
            {
                "title": "Batch Doc 2",
                "content": "Second batch document"
            }
        ]
    }
    
    response = client.post("/api/v1/documents/batch", json=batch_docs)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

def test_popular_queries():
    """Test popular queries endpoint"""
    # Perform some searches
    queries = ["python", "javascript", "python", "java", "python"]
    for q in queries:
        client.get(f"/api/v1/search/?q={q}")
        time.sleep(0.1)  # Small delay to ensure timestamps differ
    
    response = client.get("/api/v1/search/popular?period=24h&limit=3")
    assert response.status_code == 200
    data = response.json()
    
    assert "queries" in data
    assert len(data["queries"]) > 0

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_invalid_document_creation():
    """Test invalid document creation"""
    invalid_docs = [
        {},  # Empty document
        {"title": "No Content"},  # Missing content
        {"content": "No Title"},  # Missing title
        {"title": "X" * 501, "content": "Too long title"},  # Title too long
    ]
    
    for doc in invalid_docs:
        response = client.post("/api/v1/documents/", json=doc)
        assert response.status_code == 422  # Validation error

def test_search_with_filters():
    """Test search with filters"""
    response = client.get("/api/v1/search/?q=test&filters[author]=Tester")
    assert response.status_code == 200

def test_cache_clear():
    """Test cache clearing"""
    # First populate cache
    client.get("/api/v1/search/?q=cachetest")
    
    # Clear cache via admin endpoint (if available)
    # response = client.delete("/api/v1/admin/cache")
    # assert response.status_code == 200

def test_concurrent_searches():
    """Test concurrent searches"""
    import threading
    
    results = []
    
    def search_worker(query):
        response = client.get(f"/api/v1/search/?q={query}")
        results.append(response.status_code)
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=search_worker, args=(f"query{i}",))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert all(r == 200 for r in results)

if __name__ == "__main__":
    pytest.main(["-v", "test_search.py"])