"""
Documents API Routes
Handles document management operations
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
import logging
from typing import List, Optional
import asyncio

from ..services.indexing_service import IndexingService
from ..services.worker_service import WorkerService

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)

# Initialize services
indexing_service = IndexingService()
worker_service = WorkerService()

@router.post("/documents/")
async def create_document(doc: dict):
    """
    Create a new document
    """
    try:
        document = await indexing_service.create_document(doc)
        logger.info(f"Document created: {document.id}")
        
        # Index asynchronously
        asyncio.create_task(indexing_service.index_document(document))
        
        return document.to_dict()
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/batch")
async def create_documents_batch(documents: List[dict]):
    """
    Create multiple documents in batch
    """
    try:
        results = []
        for doc in documents:
            document = await indexing_service.create_document(doc)
            results.append(document.to_dict())
        
        # Index all documents asynchronously
        asyncio.create_task(indexing_service.index_documents_batch(
            [await indexing_service.get_document(r["id"]) for r in results]
        ))
        
        return results
    except Exception as e:
        logger.error(f"Error in batch creation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and index a file
    """
    try:
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Create document from file
        doc_data = {
            "title": file.filename,
            "content": text_content,
            "tags": ["uploaded"],
            "metadata": {"file_type": file.content_type}
        }
        
        document = await indexing_service.create_document(doc_data)
        
        # Index document asynchronously
        asyncio.create_task(indexing_service.index_document(document))
        
        return {
            "message": "File uploaded successfully",
            "document_id": document.id,
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """
    Get document by ID
    """
    try:
        document = await indexing_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete document by ID
    """
    try:
        success = await indexing_service.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/")
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """
    List all documents with pagination
    """
    try:
        documents = await indexing_service.list_documents(skip, limit)
        return [doc.to_dict() for doc in documents]
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))