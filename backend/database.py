import sqlite3
import contextlib
from typing import Optional, List, Dict, Any
import json
from datetime import datetime
import logging
from contextlib import contextmanager
import threading

from .config import settings

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Thread-safe database connection manager"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize database connection"""
        self.local = threading.local()
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Get thread-safe database connection"""
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(
                settings.DATABASE_URL.replace('sqlite:///', ''),
                check_same_thread=False,
                timeout=30
            )
            self.local.connection.row_factory = sqlite3.Row
        try:
            yield self.local.connection
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
    
    def _init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Documents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    tags TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    word_count INTEGER,
                    metadata TEXT
                )
            ''')
            
            # Inverted index table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inverted_index (
                    term TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    frequency INTEGER,
                    positions TEXT,
                    PRIMARY KEY (term, document_id),
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
            ''')
            
            # Search analytics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    execution_time_ms INTEGER,
                    cache_hit BOOLEAN,
                    result_count INTEGER,
                    user_agent TEXT,
                    ip_address TEXT
                )
            ''')
            
            # Document statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doc_stats (
                    document_id TEXT PRIMARY KEY,
                    view_count INTEGER DEFAULT 0,
                    search_appearances INTEGER DEFAULT 0,
                    avg_relevance_score REAL DEFAULT 0,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
                )
            ''')
            
            # Index metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_inverted_term ON inverted_index(term)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_analytics_query ON search_analytics(query)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_analytics_timestamp ON search_analytics(timestamp)')
            
            conn.commit()
            logger.info("Database initialized successfully")

db = DatabaseConnection()