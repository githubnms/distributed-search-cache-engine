from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Optional
import logging
import asyncio

from ..schemas import DocumentCreate, DocumentResponse, BatchDocumentCreate
from ..services.indexing_service import IndexingService
from ..services.worker_service import WorkerService
from ..utils.logger import get_logger

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
logger = get_logger(__name__)

indexing_service = IndexingService()
worker_service = WorkerService()

@router.post("/", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate):
    """
    Create a new document and index it
    """
    try:
        # Create document
        document = await indexing_service.create_document(doc.dict())
        
        # Index asynchronously
        asyncio.create_task(indexing_service.index_document(document))
        
        logger.info(f"Document created: {document.id}")
        return DocumentResponse.from_orm(document)
        
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating document")

@router.post("/batch", response_model=List[DocumentResponse])
async def create_documents_batch(batch: BatchDocumentCreate):
    """
    Create multiple documents in batch
    """
    try:
        documents = []
        for doc_data in batch.documents:
            doc = await indexing_service.create_document(doc_data.dict())
            documents.append(doc)
        
        # Index all documents
        asyncio.create_task(indexing_service.index_documents_batch(documents))
        
        logger.info(f"Batch created: {len(documents)} documents")
        return [DocumentResponse.from_orm(doc) for doc in documents]
        
    except Exception as e:
        logger.error(f"Error in batch creation: {str(e)}")
        raise HTTPException(status_code=500, detail="Error in batch creation")

@router.post("/upload")
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
        
        # Index document
        asyncio.create_task(indexing_service.index_document(document))
        
        logger.info(f"File uploaded and indexed: {file.filename}")
        return {
            "message": "File uploaded successfully",
            "document_id": document.id,
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error uploading file")

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document by ID
    """
    try:
        document = await indexing_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse.from_orm(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving document")

@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete document by ID
    """
    try:
        success = await indexing_service.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Remove from cache
        asyncio.create_task(indexing_service.remove_from_cache(document_id))
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail="Error deleting document")

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(skip: int = 0, limit: int = 10):
    """
    List all documents with pagination
    """
    try:
        documents = await indexing_service.list_documents(skip, limit)
        return [DocumentResponse.from_orm(doc) for doc in documents]
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Error listing documents")