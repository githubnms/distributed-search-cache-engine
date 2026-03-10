from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json

@dataclass
class Document:
    """Document model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content[:200] + '...' if len(self.content) > 200 else self.content,
            'author': self.author,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'word_count': self.word_count,
            'metadata': json.dumps(self.metadata)
        }
    
    def to_full_dict(self) -> Dict:
        """Convert to full dictionary with all content"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'word_count': self.word_count,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Document':
        """Create document from dictionary"""
        doc = cls(
            id=data.get('id', str(uuid.uuid4())),
            title=data.get('title', ''),
            content=data.get('content', ''),
            author=data.get('author'),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )
        
        if 'created_at' in data:
            doc.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            doc.updated_at = datetime.fromisoformat(data['updated_at'])
        
        doc.word_count = len(doc.content.split())
        return doc

@dataclass
class SearchResult:
    """Search result model"""
    document: Document
    relevance_score: float
    matched_terms: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'document': self.document.to_dict(),
            'relevance_score': self.relevance_score,
            'matched_terms': self.matched_terms,
            'highlights': self.highlights
        }

@dataclass
class SearchQuery:
    """Search query model"""
    query: str
    filters: Optional[Dict] = None
    limit: int = 10
    offset: int = 0
    sort_by: str = 'relevance'
    
    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'filters': self.filters,
            'limit': self.limit,
            'offset': self.offset,
            'sort_by': self.sort_by
        }

@dataclass
class AnalyticsEvent:
    """Analytics event model"""
    query: str
    execution_time_ms: float
    cache_hit: bool
    result_count: int
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'timestamp': self.timestamp.isoformat(),
            'execution_time_ms': self.execution_time_ms,
            'cache_hit': self.cache_hit,
            'result_count': self.result_count,
            'user_agent': self.user_agent,
            'ip_address': self.ip_address
        }