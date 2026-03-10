from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

class DocumentCreate(BaseModel):
    """Schema for creating a document"""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('tags', each_item=True)
    def validate_tags(cls, v):
        if not re.match(r'^[a-zA-Z0-9-_]+$', v):
            raise ValueError('Tags can only contain letters, numbers, hyphens, and underscores')
        return v.lower()

class DocumentResponse(BaseModel):
    """Schema for document response"""
    id: str
    title: str
    content: str
    author: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    word_count: int
    
    class Config:
        from_attributes = True

class SearchRequest(BaseModel):
    """Schema for search request"""
    q: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)
    filters: Optional[Dict[str, Any]] = None
    
    @validator('q')
    def sanitize_query(cls, v):
        # Remove any potentially dangerous characters
        return re.sub(r'[<>{}()]', '', v).strip()

class SearchResponse(BaseModel):
    """Schema for search response"""
    query: str
    total_results: int
    execution_time_ms: float
    cache_hit: bool
    results: List[Dict[str, Any]]

class StatsResponse(BaseModel):
    """Schema for statistics response"""
    total_searches: int
    unique_queries: int
    cache_hit_rate: float
    avg_response_time_ms: float
    total_documents: int
    index_size_mb: float
    top_queries: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]

class BatchDocumentCreate(BaseModel):
    """Schema for batch document creation"""
    documents: List[DocumentCreate]
    
    @validator('documents')
    def validate_batch_size(cls, v):
        if len(v) > 100:
            raise ValueError('Batch size cannot exceed 100 documents')
        return v

class PopularQueriesResponse(BaseModel):
    """Schema for popular queries response"""
    period: str
    queries: List[Dict[str, Any]]