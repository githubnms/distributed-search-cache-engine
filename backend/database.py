"""
Database Module
Handles database connections and initialization
"""

import sqlite3
import contextlib
from typing import Optional, List, Dict, Any
import json
from datetime import datetime
import logging
from contextlib import contextmanager
import threading
import os
from pathlib import Path

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
        self.db_path = self._get_database_path()
        self._ensure_data_directory()
        self._init_db()
        logger.info(f"✅ Database initialized at: {self.db_path}")
    
    def _get_database_path(self):
        """Get the correct database path"""
        # Get the project root directory (where backend folder is)
        current_file = Path(__file__).resolve()  # backend/database.py
        project_root = current_file.parent.parent  # Go up two levels to project root
        
        # Create data directory path
        data_dir = project_root / 'data'
        db_path = data_dir / 'dsce.db'
        
        return str(db_path)
    
    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"📁 Created data directory: {db_dir}")
    
    @contextmanager
    def get_connection(self):
        """Get thread-safe database connection"""
        try:
            if not hasattr(self.local, 'connection'):
                self.local.connection = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=30
                )
                self.local.connection.row_factory = sqlite3.Row
                logger.debug(f"🔌 Database connection established")
            
            yield self.local.connection
            
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Database connection error: {e}")
            logger.error(f"   Path: {self.db_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
            raise
    
    def _init_db(self):
        """Initialize database tables"""
        try:
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
                logger.info("✅ Database tables created successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    def close_all_connections(self):
        """Close all database connections"""
        if hasattr(self.local, 'connection'):
            self.local.connection.close()
            delattr(self.local, 'connection')
            logger.info("🔌 Database connection closed")

# Create global instance - THIS IS THE IMPORTANT PART
db = DatabaseConnection()

# Export the db instance
__all__ = ['db']