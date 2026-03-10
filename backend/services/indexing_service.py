import asyncio
from typing import List, Dict, Any, Optional
from collections import defaultdict
import json
from datetime import datetime
import logging
import math

from ..models import Document
from ..database import db
from ..utils.tokenizer import Tokenizer
from ..config import settings

logger = logging.getLogger(__name__)

class IndexingService:
    """Service for document indexing and management"""
    
    def __init__(self):
        self.tokenizer = Tokenizer()
        self.index_lock = asyncio.Lock()
        self.inverted_index = defaultdict(dict)  # term -> {doc_id: frequency}
        self.documents = {}
        self.shards = settings.SHARD_CONFIG
        
    async def create_document(self, doc_data: Dict) -> Document:
        """Create a new document"""
        document = Document.from_dict(doc_data)
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents (id, title, content, author, tags, created_at, updated_at, word_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                document.id,
                document.title,
                document.content,
                document.author,
                json.dumps(document.tags),
                document.created_at.isoformat(),
                document.updated_at.isoformat(),
                document.word_count,
                json.dumps(document.metadata)
            ))
            conn.commit()
        
        return document
    
    async def index_document(self, document: Document):
        """Index a single document"""
        async with self.index_lock:
            try:
                # Tokenize content
                tokens = self.tokenizer.tokenize(document.content)
                term_frequencies = defaultdict(int)
                
                for token in tokens:
                    term_frequencies[token] += 1
                
                # Update inverted index
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    for term, freq in term_frequencies.items():
                        cursor.execute('''
                            INSERT OR REPLACE INTO inverted_index (term, document_id, frequency)
                            VALUES (?, ?, ?)
                        ''', (term, document.id, freq))
                        
                        # Update in-memory index
                        self.inverted_index[term][document.id] = freq
                    
                    conn.commit()
                
                # Store document in memory
                self.documents[document.id] = document
                
                logger.info(f"Indexed document {document.id} with {len(term_frequencies)} unique terms")
                
            except Exception as e:
                logger.error(f"Error indexing document {document.id}: {str(e)}")
                raise
    
    async def index_documents_batch(self, documents: List[Document]):
        """Index multiple documents in batch"""
        tasks = [self.index_document(doc) for doc in documents]
        await asyncio.gather(*tasks)
        logger.info(f"Batch indexed {len(documents)} documents")
    
    async def search(self, query: str, limit: int = 10, offset: int = 0) -> List[Document]:
        """Search for documents matching query"""
        try:
            # Tokenize query
            query_terms = self.tokenizer.tokenize(query)
            
            if not query_terms:
                return []
            
            # Get matching documents from inverted index
            doc_scores = defaultdict(float)
            matched_terms = defaultdict(list)
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                for term in query_terms:
                    cursor.execute('''
                        SELECT document_id, frequency FROM inverted_index
                        WHERE term = ?
                    ''', (term,))
                    
                    for row in cursor.fetchall():
                        doc_id = row['document_id']
                        frequency = row['frequency']
                        
                        # Calculate TF-IDF score
                        doc_scores[doc_id] += frequency * math.log(10000 / (frequency + 1))
                        matched_terms[doc_id].append(term)
            
            # Sort by score and apply pagination
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            paginated_docs = sorted_docs[offset:offset + limit]
            
            # Fetch full documents
            results = []
            for doc_id, score in paginated_docs:
                doc = await self.get_document(doc_id)
                if doc:
                    doc.relevance_score = score
                    doc.matched_terms = matched_terms[doc_id]
                    results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return []
    
    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID"""
        # Check memory cache first
        if doc_id in self.documents:
            return self.documents[doc_id]
        
        # Check database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
            row = cursor.fetchone()
            
            if row:
                doc_data = dict(row)
                doc_data['tags'] = json.loads(doc_data['tags'])
                doc_data['metadata'] = json.loads(doc_data['metadata'])
                document = Document.from_dict(doc_data)
                self.documents[doc_id] = document
                return document
        
        return None
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete document by ID"""
        async with self.index_lock:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Remove from inverted index
                    cursor.execute('DELETE FROM inverted_index WHERE document_id = ?', (doc_id,))
                    
                    # Remove document
                    cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
                    
                    conn.commit()
                
                # Remove from memory
                if doc_id in self.documents:
                    del self.documents[doc_id]
                
                # Remove from inverted index memory
                for term in list(self.inverted_index.keys()):
                    if doc_id in self.inverted_index[term]:
                        del self.inverted_index[term][doc_id]
                
                logger.info(f"Deleted document {doc_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error deleting document {doc_id}: {str(e)}")
                return False
    
    async def list_documents(self, skip: int = 0, limit: int = 10) -> List[Document]:
        """List all documents with pagination"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM documents
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, skip))
            
            documents = []
            for row in cursor.fetchall():
                doc_data = dict(row)
                doc_data['tags'] = json.loads(doc_data['tags'])
                doc_data['metadata'] = json.loads(doc_data['metadata'])
                documents.append(Document.from_dict(doc_data))
            
            return documents
    
    async def get_index_statistics(self) -> Dict:
        """Get index statistics"""
        stats = {
            'total_documents': 0,
            'size_mb': 0,
            'documents_per_shard': {},
            'unique_terms': 0,
            'avg_doc_size': 0
        }
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total documents
            cursor.execute('SELECT COUNT(*) as count FROM documents')
            stats['total_documents'] = cursor.fetchone()['count']
            
            # Unique terms
            cursor.execute('SELECT COUNT(DISTINCT term) as count FROM inverted_index')
            stats['unique_terms'] = cursor.fetchone()['count']
            
            # Average document size
            cursor.execute('SELECT AVG(word_count) as avg FROM documents')
            stats['avg_doc_size'] = cursor.fetchone()['avg'] or 0
            
            # Documents per shard (simulated)
            for shard_name, shard_config in self.shards.items():
                start, end = shard_config['range']
                cursor.execute('''
                    SELECT COUNT(*) as count FROM documents
                    WHERE substr(title, 1, 1) BETWEEN ? AND ?
                ''', (start, end))
                stats['documents_per_shard'][shard_name] = cursor.fetchone()['count']
        
        return stats
    
    async def remove_from_cache(self, doc_id: str):
        """Remove document from cache"""
        # Implementation for cache removal
        pass
    
    async def check_health(self) -> bool:
        """Check database health"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                return True
        except:
            return False