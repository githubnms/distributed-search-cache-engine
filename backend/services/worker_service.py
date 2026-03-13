"""
Worker Service Module
Handles background tasks and asynchronous processing
"""

import asyncio
import logging
from typing import Dict, Any, List, Callable
from datetime import datetime
import json

from ..models import Document
from ..services.indexing_service import IndexingService
from ..services.cache_service import CacheService

logger = logging.getLogger(__name__)

class WorkerService:
    """
    Service for managing background workers and async tasks
    """
    
    def __init__(self):
        self.indexing_service = IndexingService()
        self.cache_service = CacheService()
        self.tasks = {}
        self.task_results = {}
        self.workers = {}
        self.is_running = False
        
    async def start(self):
        """Start the worker service"""
        self.is_running = True
        logger.info("Worker service started")
        
    async def stop(self):
        """Stop the worker service"""
        self.is_running = False
        
        # Cancel all tasks
        for task_id, task in self.tasks.items():
            task.cancel()
        
        logger.info("Worker service stopped")
    
    async def submit_task(self, task_type: str, data: Any) -> str:
        """
        Submit a task for background processing
        
        Args:
            task_type: Type of task (index, cache_warm, etc.)
            data: Task data
            
        Returns:
            Task ID string
        """
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # Create task
        task = {
            'id': task_id,
            'type': task_type,
            'data': data,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.tasks[task_id] = task
        
        # Start processing
        asyncio.create_task(self._process_task(task_id))
        
        logger.info(f"Task submitted: {task_id} - {task_type}")
        return task_id
    
    async def _process_task(self, task_id: str):
        """
        Process a background task
        
        Args:
            task_id: Task ID to process
        """
        if task_id not in self.tasks:
            logger.error(f"Task not found: {task_id}")
            return
        
        task = self.tasks[task_id]
        task['status'] = 'processing'
        task['updated_at'] = datetime.now().isoformat()
        
        try:
            # Process based on task type
            if task['type'] == 'index_document':
                result = await self._process_index_document(task['data'])
            elif task['type'] == 'batch_index':
                result = await self._process_batch_index(task['data'])
            elif task['type'] == 'cache_warm':
                result = await self._process_cache_warm(task['data'])
            elif task['type'] == 'rebuild_index':
                result = await self._process_rebuild_index()
            else:
                raise ValueError(f"Unknown task type: {task['type']}")
            
            # Store result
            task['status'] = 'completed'
            task['result'] = result
            task['completed_at'] = datetime.now().isoformat()
            
            logger.info(f"Task completed: {task_id}")
            
        except Exception as e:
            logger.error(f"Task failed: {task_id} - {str(e)}")
            task['status'] = 'failed'
            task['error'] = str(e)
            task['failed_at'] = datetime.now().isoformat()
        
        task['updated_at'] = datetime.now().isoformat()
    
    async def _process_index_document(self, data: Dict) -> Dict:
        """
        Process document indexing task
        
        Args:
            data: Document data
            
        Returns:
            Indexing result
        """
        try:
            # Create document
            document = await self.indexing_service.create_document(data)
            
            # Index document
            await self.indexing_service.index_document(document)
            
            return {
                'document_id': document.id,
                'status': 'indexed',
                'word_count': document.word_count
            }
            
        except Exception as e:
            logger.error(f"Index document error: {str(e)}")
            raise
    
    async def _process_batch_index(self, documents: List[Dict]) -> Dict:
        """
        Process batch indexing task
        
        Args:
            documents: List of documents to index
            
        Returns:
            Batch indexing result
        """
        try:
            results = []
            for doc_data in documents:
                result = await self._process_index_document(doc_data)
                results.append(result)
            
            return {
                'total': len(results),
                'successful': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Batch index error: {str(e)}")
            raise
    
    async def _process_cache_warm(self, queries: List[str]) -> Dict:
        """
        Process cache warming task
        
        Args:
            queries: List of queries to cache
            
        Returns:
            Cache warming result
        """
        try:
            warmed = 0
            for query in queries:
                # Search and cache
                results = await self.indexing_service.search(query, limit=20)
                if results:
                    await self.cache_service.cache_results(query, results)
                    warmed += 1
            
            return {
                'total_queries': len(queries),
                'warmed': warmed
            }
            
        except Exception as e:
            logger.error(f"Cache warm error: {str(e)}")
            raise
    
    async def _process_rebuild_index(self) -> Dict:
        """
        Process index rebuild task
        
        Returns:
            Rebuild result
        """
        try:
            # Get all documents
            documents = await self.indexing_service.list_documents(limit=10000)
            
            # Clear existing index
            self.indexing_service.inverted_index.clear()
            
            # Reindex all documents
            for doc in documents:
                await self.indexing_service.index_document(doc)
            
            return {
                'documents_reindexed': len(documents),
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Rebuild index error: {str(e)}")
            raise
    
    async def get_task_status(self, task_id: str) -> Dict:
        """
        Get status of a task
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status dictionary
        """
        return self.tasks.get(task_id, {'error': 'Task not found'})
    
    async def list_tasks(self, status: str = None) -> List[Dict]:
        """
        List all tasks
        
        Args:
            status: Filter by status
            
        Returns:
            List of tasks
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t['status'] == status]
        
        return tasks
    
    async def clear_completed_tasks(self, older_than_hours: int = 24):
        """
        Clear completed tasks older than specified hours
        
        Args:
            older_than_hours: Age threshold in hours
        """
        from datetime import datetime, timedelta
        
        threshold = datetime.now() - timedelta(hours=older_than_hours)
        
        to_delete = []
        for task_id, task in self.tasks.items():
            if task['status'] in ['completed', 'failed']:
                completed_at = datetime.fromisoformat(task.get('completed_at', task['created_at']))
                if completed_at < threshold:
                    to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.tasks[task_id]
        
        logger.info(f"Cleared {len(to_delete)} completed tasks")
    
    async def health_check(self) -> bool:
        """
        Check worker service health
        
        Returns:
            True if healthy
        """
        return self.is_running