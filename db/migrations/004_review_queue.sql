-- Migration 004: Ambiguity Review Queue & Normalization Log
-- Adheres to Law 6 (No silent ambiguity), Gate G3 (Zero silent resolutions)

CREATE TABLE IF NOT EXISTS ambiguity_review_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_input TEXT NOT NULL,
    cleaned_query TEXT NOT NULL,
    reason_code TEXT NOT NULL, -- AMBIGUOUS_STRENGTH, UNRECOGNIZED_BRAND, MULTIPLE_FORMULATION_MATCH, UNRESOLVED_PACK_TOKEN
    candidate_matches_json TEXT,
    confidence REAL NOT NULL,
    method_tag TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING_REVIEW', -- PENDING_REVIEW, RESOLVED, REJECTED
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS normalization_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_input TEXT NOT NULL,
    resolved_product_id TEXT,
    resolved_brand_name TEXT,
    confidence REAL NOT NULL,
    method_tag TEXT NOT NULL, -- EXACT_MATCH, TOKEN_NORMALIZED, HEURISTIC_SYNTHETIC, REVIEW_QUEUED
    status TEXT NOT NULL, -- RESOLVED, QUEUED_FOR_REVIEW
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
