-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create tables
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author TEXT,
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    word_count INTEGER,
    is_indexed BOOLEAN DEFAULT FALSE,
    search_vector tsvector
);

CREATE TABLE IF NOT EXISTS search_analytics (
    id BIGSERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    execution_time_ms INTEGER,
    cache_hit BOOLEAN,
    result_count INTEGER,
    user_agent TEXT,
    ip_address INET,
    session_id UUID
);

CREATE TABLE IF NOT EXISTS cache_stats (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    hits BIGINT,
    misses BIGINT,
    hit_rate FLOAT,
    memory_used_bytes BIGINT,
    keys_count INTEGER
);

-- Create indexes
CREATE INDEX idx_documents_search_vector ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_search_analytics_timestamp ON search_analytics(timestamp DESC);
CREATE INDEX idx_search_analytics_query ON search_analytics(query);

-- Create update trigger for search vector
CREATE OR REPLACE FUNCTION documents_search_vector_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.tags, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_search_vector_update
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_search_vector_update();

-- Create partitioned table for analytics
CREATE TABLE IF NOT EXISTS search_analytics_partitioned (
    LIKE search_analytics INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
) PARTITION BY RANGE (timestamp);

-- Create partitions for last 30 days
DO $$
DECLARE
    i INTEGER;
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..30 LOOP
        start_date := CURRENT_DATE - (i * INTERVAL '1 day');
        end_date := start_date + INTERVAL '1 day';
        partition_name := 'search_analytics_' || TO_CHAR(start_date, 'YYYY_MM_DD');
        
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF search_analytics_partitioned
            FOR VALUES FROM (%L) TO (%L)
        ', partition_name, start_date, end_date);
    END LOOP;
END $$;