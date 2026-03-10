"""
API package initialization
"""
from fastapi import APIRouter

api_router = APIRouter()

from . import search, documents, stats