"""
Ranking Service Module
Handles document ranking and relevance scoring
"""

from typing import List, Dict, Any
import logging
import math
from collections import Counter

from ..models import Document

logger = logging.getLogger(__name__)

class RankingService:
    """
    Service for ranking search results
    Implements TF-IDF and other relevance scoring algorithms
    """
    
    def __init__(self):
        self.idf_cache = {}
        
    async def rank_results(self, documents: List[Document], query: str) -> List[Document]:
        """
        Rank documents by relevance to query
        
        Args:
            documents: List of documents to rank
            query: Search query string
            
        Returns:
            Ranked list of documents
        """
        try:
            if not documents:
                return []
            
            # Calculate scores for each document
            scored_docs = []
            for doc in documents:
                score = await self._calculate_relevance_score(doc, query)
                doc.relevance_score = score
                scored_docs.append((doc, score))
            
            # Sort by score descending
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            # Return sorted documents
            return [doc for doc, _ in scored_docs]
            
        except Exception as e:
            logger.error(f"Ranking error: {str(e)}")
            return documents
    
    async def _calculate_relevance_score(self, document: Document, query: str) -> float:
        """
        Calculate relevance score for a document
        
        Args:
            document: Document to score
            query: Search query string
            
        Returns:
            Relevance score between 0 and 1
        """
        try:
            score = 0.0
            weights = {
                'title': 0.4,
                'content': 0.3,
                'tags': 0.2,
                'recency': 0.1
            }
            
            # Title match (highest weight)
            title_score = self._calculate_field_match(document.title, query)
            score += title_score * weights['title']
            
            # Content match
            content_score = self._calculate_field_match(document.content, query)
            score += content_score * weights['content']
            
            # Tags match
            tags_text = ' '.join(document.tags) if document.tags else ''
            tags_score = self._calculate_field_match(tags_text, query)
            score += tags_score * weights['tags']
            
            # Recency bonus
            recency_score = await self._calculate_recency_score(document)
            score += recency_score * weights['recency']
            
            # Normalize score to 0-1 range
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Score calculation error: {str(e)}")
            return 0.0
    
    def _calculate_field_match(self, field_text: str, query: str) -> float:
        """
        Calculate how well a text field matches the query
        
        Args:
            field_text: Text content to match against
            query: Search query
            
        Returns:
            Match score between 0 and 1
        """
        if not field_text or not query:
            return 0.0
        
        field_text = field_text.lower()
        query = query.lower()
        
        # Exact match bonus
        if query in field_text:
            exact_match_bonus = 0.3
        else:
            exact_match_bonus = 0.0
        
        # Term frequency
        query_terms = query.split()
        if not query_terms:
            return 0.0
        
        term_matches = 0
        for term in query_terms:
            if term in field_text:
                term_matches += field_text.count(term)
        
        max_possible = len(field_text.split()) if field_text.split() else 1
        tf_score = min(1.0, term_matches / max_possible) if max_possible > 0 else 0.0
        
        # Combine scores
        return min(1.0, tf_score + exact_match_bonus)
    
    async def _calculate_recency_score(self, document: Document) -> float:
        """
        Calculate recency score for a document
        
        Args:
            document: Document to evaluate
            
        Returns:
            Recency score between 0 and 1
        """
        try:
            from datetime import datetime, timedelta
            
            if not document.created_at:
                return 0.5  # Default score if no date
            
            now = datetime.utcnow()
            doc_date = document.created_at
            
            # Calculate age in days
            age_days = (now - doc_date).days
            
            if age_days < 7:  # Less than a week old
                return 1.0
            elif age_days < 30:  # Less than a month old
                return 0.8
            elif age_days < 90:  # Less than 3 months old
                return 0.6
            elif age_days < 365:  # Less than a year old
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            logger.error(f"Recency score error: {str(e)}")
            return 0.5
    
    async def get_ranking_explanation(self, document: Document, query: str) -> Dict[str, Any]:
        """
        Get explanation of how a document was ranked
        
        Args:
            document: Document to explain
            query: Search query
            
        Returns:
            Dictionary with ranking explanation
        """
        try:
            explanation = {
                'document_id': document.id,
                'title': document.title,
                'query': query,
                'scores': {
                    'title': self._calculate_field_match(document.title, query),
                    'content': self._calculate_field_match(document.content, query),
                    'tags': self._calculate_field_match(' '.join(document.tags), query) if document.tags else 0,
                    'recency': await self._calculate_recency_score(document)
                }
            }
            
            # Calculate final score with weights
            weights = {'title': 0.4, 'content': 0.3, 'tags': 0.2, 'recency': 0.1}
            final_score = sum(explanation['scores'][k] * weights[k] for k in weights)
            explanation['final_score'] = min(1.0, final_score)
            
            return explanation
            
        except Exception as e:
            logger.error(f"Ranking explanation error: {str(e)}")
            return {'error': str(e)}