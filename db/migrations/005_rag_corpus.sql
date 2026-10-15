-- Migration 005: RAG Clinical Decision Units Corpus
-- Adheres to Section 3 Module B.1 (Clinically meaningful decision units, never blind token slices)

CREATE TABLE IF NOT EXISTS clinical_decision_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_code TEXT NOT NULL,
    title TEXT NOT NULL,
    specialty TEXT NOT NULL,
    version TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    supersedes TEXT,
    section TEXT NOT NULL, -- ASSESS, FIRST-LINE MANAGEMENT, RED FLAGS, AVOID, etc.
    decision_type TEXT NOT NULL, -- RECOMMENDATION, CONTRAINDICATION, RED_FLAG_REFERRAL, DIAGNOSIS
    page_anchor TEXT DEFAULT 'Page 1',
    content TEXT NOT NULL,
    keywords TEXT,
    is_local_protocol INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunk_doc_code ON clinical_decision_chunks(doc_code);
CREATE INDEX IF NOT EXISTS idx_chunk_specialty ON clinical_decision_chunks(specialty);
CREATE INDEX IF NOT EXISTS idx_chunk_section ON clinical_decision_chunks(section);
