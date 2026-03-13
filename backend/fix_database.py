# fix_database.py
import sqlite3
import os

# Fix database schema
db_path = 'data/dsce.db'
if os.path.exists(db_path):
    # Backup existing db
    os.rename(db_path, db_path + '.backup')
    print(f"Backed up existing database to {db_path}.backup")

# Create new database with correct schema
conn = sqlite3.connect(db_path)
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

conn.commit()
conn.close()
print("✅ Database fixed successfully!")