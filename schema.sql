-- schema.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Tenders
CREATE TABLE IF NOT EXISTS tenders (
    tender_id SERIAL PRIMARY KEY,
    tender_title TEXT NOT NULL,
    tender_reference_number TEXT UNIQUE NOT NULL,
    issuing_authority TEXT,
    submission_deadline TIMESTAMP,
    site_location TEXT,
    contract_type TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Criteria Register
CREATE TABLE IF NOT EXISTS criteria_register (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    example TEXT,
    created_by_qs BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tender Qualification Criteria (Updated with justification and actions)
CREATE TABLE IF NOT EXISTS tender_qualification_criteria (
    criteria_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES criteria_register(tag_id),
    raw_text TEXT NOT NULL,
    normalized_text TEXT,
    confidence_score DECIMAL(3,2),
    is_met BOOLEAN DEFAULT NULL,
    justification TEXT,
    actions TEXT,  -- JSON array string, e.g., '["Action 1", "Action 2"]'
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tender_id, tag_id)
);

-- GDrive Tracking
CREATE TABLE IF NOT EXISTS gdrive_file_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gdrive_file_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    processing_status VARCHAR(50) DEFAULT 'pending',
    tender_id INTEGER REFERENCES tenders(tender_id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(gdrive_file_id, file_hash)
);

-- Document Chunks
CREATE TABLE IF NOT EXISTS tender_document_chunks (
    chunk_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_name TEXT,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    embedding vector(1024),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Company Knowledge (Hybrid FTS)
CREATE TABLE IF NOT EXISTS company_knowledge (
    knowledge_id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    is_met BOOLEAN DEFAULT FALSE,
    notes TEXT,
    search_text TSVECTOR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- FTS index
CREATE INDEX IF NOT EXISTS idx_knowledge_fts ON company_knowledge USING GIN(search_text);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_search_text() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_text := to_tsvector('english', COALESCE(NEW.description, '') || ' ' || COALESCE(NEW.notes, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_search_text
BEFORE INSERT OR UPDATE ON company_knowledge
FOR EACH ROW EXECUTE PROCEDURE update_search_text();