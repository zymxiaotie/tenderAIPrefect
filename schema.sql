-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Tenders
CREATE TABLE IF NOT EXISTS tenders (
    tender_id SERIAL PRIMARY KEY,
    tender_title TEXT NOT NULL,
    tender_reference_number TEXT UNIQUE NOT NULL,
    issuing_authority TEXT,
    submission_deadline TIMESTAMP,
    clarification_deadline TIMESTAMP,
    site_location TEXT,
    project_name TEXT,
    contract_type TEXT,
    liquidated_damages TEXT,
    performance_bond TEXT,
    retention TEXT,
    defects_liability_period TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Criteria Register (Master Tags)
CREATE TABLE IF NOT EXISTS criteria_register (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    example TEXT,
    created_by_qs BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. Tender Qualification Criteria
CREATE TABLE IF NOT EXISTS tender_qualification_criteria (
    criteria_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES criteria_register(tag_id),
    raw_text TEXT NOT NULL,
    normalized_text TEXT,
    confidence_score DECIMAL(3,2),
    source_page INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tender_id, tag_id)
);

-- 4. Google Drive File Tracking
CREATE TABLE IF NOT EXISTS gdrive_file_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gdrive_file_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    processing_status VARCHAR(50) DEFAULT 'pending',
    tender_id INTEGER REFERENCES tenders(tender_id),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    successfully_processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(gdrive_file_id, file_hash)
);

-- 5. Tender Document Chunks (for RAG)
CREATE TABLE IF NOT EXISTS tender_document_chunks (
    chunk_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_name TEXT,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    embedding vector(1024),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Document Register (Client-Issued Docs)
CREATE TABLE IF NOT EXISTS tender_documents (
    doc_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    document_name TEXT NOT NULL,
    category VARCHAR(50) NOT NULL, -- Administrative, Technical, etc.
    is_mandatory BOOLEAN DEFAULT TRUE,
    received_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tender_id, document_name)
);

-- 7. Addenda
CREATE TABLE IF NOT EXISTS tender_addenda (
    addendum_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    issued_date DATE NOT NULL,
    impact_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 8. Action Items
CREATE TABLE IF NOT EXISTS tender_action_items (
    action_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    type VARCHAR(50) NOT NULL, -- Technical, Financial, etc.
    priority VARCHAR(20) NOT NULL, -- urgent, high, medium, low
    owner TEXT,
    system_action TEXT,
    status VARCHAR(20) DEFAULT 'open', -- open, in_progress, completed
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 9. Compliance Status (Optional: for future)
CREATE TABLE IF NOT EXISTS compliance_status (
    status_id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(tender_id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES criteria_register(tag_id),
    is_met BOOLEAN,
    notes TEXT,
    validated_by TEXT,
    validated_at TIMESTAMP,
    UNIQUE(tender_id, tag_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON tender_document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_tracking_hash ON gdrive_file_tracking(file_hash);
CREATE INDEX IF NOT EXISTS idx_criteria_tender ON tender_qualification_criteria(tender_id);
CREATE INDEX IF NOT EXISTS idx_docs_tender ON tender_documents(tender_id);