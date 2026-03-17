"""
API Package
Exports all routers
"""

from . import search
from . import documents
from . import stats

__all__ = ['search', 'documents', 'stats']